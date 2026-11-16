"""s3c-secret-scan 검증. python check.py [--model]"""
import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "tools"))
from octest import Sandbox, check, finish, model_check, model_enabled, skill_loaded  # noqa: E402
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fake_llm import FakeLLM  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
SANDBOX = HERE / "sandbox"
SCRIPT_REL = ".opencode/skills/secret-scan/scripts/scan_secrets.py"


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



def onerror(func, path, _exc):
    os.chmod(path, stat.S_IWRITE)
    func(path)


# Fake secret values come from prepare.py (built at runtime), never from literals in this file.
spec = importlib.util.spec_from_file_location("s3c_prepare", HERE / "prepare.py")
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)
SECRETS = prepare.make_secrets()

try:
    # No token-shaped literal is committed anywhere in this example.
    tracked = [p for p in HERE.rglob("*") if p.is_file() and "sandbox" not in p.parts and "__pycache__" not in p.parts
               and "node_modules" not in p.parts]
    leaks = [str(p.relative_to(HERE)) for p in tracked
             if any(v in p.read_text(encoding="utf-8", errors="replace") for v in SECRETS.values())]
    check("no fake secret value is written in any committed file", not leaks, str(leaks))

    p = run("prepare.py")
    check("prepare.py runs", p.returncode == 0 and (SANDBOX / ".env").is_file(), p.stderr)

    h = run(SCRIPT_REL, "--help", cwd=SANDBOX)
    check("script --help exits 0", h.returncode == 0 and "--changed" in h.stdout, h.stderr)

    p = run(SCRIPT_REL, cwd=SANDBOX)
    out = p.stdout
    check("findings -> exit code 1", p.returncode == 1, f"{p.returncode} {p.stderr}")
    for rule in ("hardcoded-credential", "known-token-prefix", "url-credentials", "private-key-header",
                 "env-file", "env-secret", "high-entropy-string"):
        check(f"rule {rule} fires", f":{rule}:" in out, out[:600])
    check("format is file:line:rule", "config.py:3:hardcoded-credential:" in out, out[:400])
    leaked = [k for k, v in SECRETS.items() if v in out or v in p.stderr]
    check("secret values are masked in the output", not leaked, str(leaked))
    check("placeholder / ignored lines are skipped",
          "SMTP_PASSWORD" not in out and "hunter2" not in out and "notes.md:5" not in out, out)
    check(".env.example and app.py are clean", ".env.example:" not in out and "app.py:" not in out)

    j = json.loads(run(SCRIPT_REL, "--format", "json", cwd=SANDBOX).stdout)
    check("--format json works", j["scanned_files"] > 5 and len(j["findings"]) >= 8)
    leaked = [k for k, v in SECRETS.items() if v in json.dumps(j)]
    check("json output masked too", not leaked, str(leaked))

    p = run(SCRIPT_REL, "--changed", cwd=SANDBOX)
    check("--changed finds staged + untracked files", p.returncode == 1 and "config.py:" in p.stdout
          and ".env:" in p.stdout and "app.py:" not in p.stdout, p.stdout[:400])

    p = run(SCRIPT_REL, "app.py", ".env.example", "README.md", cwd=SANDBOX)
    check("clean files -> exit code 0", p.returncode == 0 and p.stdout.startswith("# 0 finding"), p.stdout)
    p = run(SCRIPT_REL, "no-such-file", cwd=SANDBOX)
    check("missing path -> exit code 2", p.returncode == 2 and "error" in p.stderr, p.stderr)
    nongit = tempfile.mkdtemp(prefix="s3c-notgit-")
    try:
        p = run(str(SANDBOX / SCRIPT_REL), "--changed", cwd=nongit)
        check("--changed outside a git repo -> exit code 2", p.returncode == 2, p.stdout + p.stderr)
    finally:
        shutil.rmtree(nongit, ignore_errors=True)

    with Sandbox("s3c") as sb:
        skills = sb.debug_skills(cwd=SANDBOX)
        found = [s for s in skills if s["name"] == "secret-scan"]
        check("skill discovered in sandbox", bool(found))
        check("description has Korean triggers", bool(found) and "비밀값 검사" in found[0]["description"])
        scripted_skill_run(sb, SANDBOX, 'secret-scan', f"python {(SANDBOX / SCRIPT_REL).as_posix()} --changed", "known-token-prefix", 'secret-scan')
        if model_enabled():
            out = sb.run_model("secret-scan 스킬을 사용해서 커밋하기 전에 비밀값이 섞였는지 검사하고, 어떻게 고치면 되는지 알려줘. 파일은 고치지 마.",
                               cwd=SANDBOX)
            model_check("model loaded the skill", out, skill_loaded(out, "secret-scan"))
            model_check("model ran the bundled script", out, "scan_secrets.py" in out)
            model_check("answer suggests env vars and does not leak values", out,
                        ("환경 변수" in out or "env" in out.lower()) and not any(v in out for v in SECRETS.values()))
finally:
    shutil.rmtree(SANDBOX, onerror=onerror)

finish()
