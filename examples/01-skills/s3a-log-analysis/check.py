"""s3a-log-analysis 검증. python check.py [--model]"""
import hashlib
import json
import re
import shutil
import subprocess
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "tools"))
from octest import Sandbox, check, finish, model_check, model_enabled, skill_loaded  # noqa: E402
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fake_llm import FakeLLM  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
SKILL = HERE / ".opencode" / "skills" / "log-analysis"
SCRIPT = SKILL / "scripts" / "summarize_log.py"
LOG = HERE / "logs" / "app.log"


def run(*args, cwd=HERE):
    return subprocess.run([sys.executable, "-X", "utf8", *map(str, args)], cwd=cwd,
                          capture_output=True, text=True, encoding="utf-8", timeout=60)


def scripted_skill_run(sb, cwd, skill, command, marker, label):
    """가짜 모델이 skill 도구 -> bash 도구 순서로 호출하게 하고, opencode 가 돌려준 결과를 검사한다."""
    script = [("tool", "skill", {"name": skill}),
              ("tool", "bash", {"command": command, "description": "run bundled script"}), "DONE"]
    with FakeLLM(script=script) as llm:
        proc = sb.opencode(["run", "-m", "fake/echo", "--auto", "go"], cwd, timeout=300,
                           extra_env={"OPENCODE_CONFIG_CONTENT": json.dumps(llm.provider_config()), "PWD": str(cwd)})
        reqs = llm.main_requests()
    tool_msgs = [llm.message_text(m) for r in reqs[-1:] for m in r["messages"] if m["role"] == "tool"]
    skill_msg = next((t for t in tool_msgs if "<skill_content" in t), "")
    script_msg = tool_msgs[-1] if len(tool_msgs) > 1 else ""
    base = re.search(r"Base directory for this skill: (.+)", skill_msg)
    check(f"[fake model] {label}: skill tool returns SKILL.md + base directory", bool(base) and "scripts" in skill_msg,
          skill_msg[-300:] + proc.stderr[-300:])
    if base:
        print(f"       info: base directory line = {base.group(1).strip()}", flush=True)
    check(f"[fake model] {label}: bash tool ran the bundled script", marker in script_msg, script_msg[:400] + proc.stderr[-300:])


try:
    # --- no model needed ---------------------------------------------------
    p = run("prepare.py")
    check("prepare.py runs", p.returncode == 0 and LOG.is_file(), p.stderr)
    first = hashlib.sha256(LOG.read_bytes()).hexdigest()
    n_lines = len(LOG.read_text(encoding="utf-8").splitlines())
    check("log has ~2,000 lines", 1800 <= n_lines <= 2300, str(n_lines))
    run("prepare.py")
    check("prepare.py is deterministic", hashlib.sha256(LOG.read_bytes()).hexdigest() == first)

    h = run(SCRIPT, "--help")
    check("script --help exits 0", h.returncode == 0 and "--window" in h.stdout, h.stderr)

    p = run(SCRIPT, "logs/app.log", "--window", "5m", "--top", "10")
    check("script exits 0", p.returncode == 0, p.stderr)
    data = json.loads(p.stdout) if p.returncode == 0 else {}
    check("levels counted", {"INFO", "ERROR", "WARN"} <= set(data.get("levels", {})))
    inc = (data.get("incidents") or [{}])[0]
    check("incident found 10:40-10:55", inc.get("start") == "2026-11-03T10:40:00"
          and inc.get("end") == "2026-11-03T10:55:00", json.dumps(data.get("incidents"))[:300])
    check("incident is payment", (inc.get("top_components") or [{}])[0].get("name") == "payment")
    top0 = (data.get("top_errors") or [{}])[0]
    check("top error normalised (numbers masked)", top0.get("message", "").startswith("gateway timeout after <N>ms"),
          str(top0))
    check("output is small", len(p.stdout) < 12000, str(len(p.stdout)))

    p = run(SCRIPT, "logs/app.log", "--from", "2026-11-03T10:30:00", "--to", "2026-11-03T10:40:00", "--sample", "5")
    d2 = json.loads(p.stdout)
    check("time filter + sample lines work", d2["time_range"]["last"] < "2026-11-03T10:40:01" and d2["sample_lines"], p.stdout[:300])

    p = run(SCRIPT, "logs/does-not-exist.log")
    check("missing file exits 2", p.returncode == 2 and "error" in p.stderr)

    with Sandbox("s3a") as sb:
        skills = sb.debug_skills(cwd=HERE)
        found = [s for s in skills if s["name"] == "log-analysis"]
        check("skill discovered", bool(found))
        check("description has Korean triggers", bool(found) and "로그 분석" in found[0]["description"])
        scripted_skill_run(sb, HERE, 'log-analysis', f"python {(SKILL / 'scripts/summarize_log.py').as_posix()} logs/app.log --window 5m --top 3", "incidents", 'log-analysis')
        check("skill body points to bundled script", bool(found) and "scripts/summarize_log.py" in found[0]["content"])

        if model_enabled():
            out = sb.run_model("log-analysis 스킬을 사용해서 logs/app.log 의 장애 원인을 분석해줘. 파일이 크니까 전체를 읽지는 마.", cwd=HERE)
            model_check("model loaded the skill", out, skill_loaded(out, "log-analysis"))
            model_check("model ran the bundled script", out, "summarize_log.py" in out)
            model_check("answer names the payment incident", out, "payment" in out.lower() and "10:4" in out)
finally:
    shutil.rmtree(HERE / "logs", ignore_errors=True)

finish()
