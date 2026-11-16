"""s4b-mermaid-diagram 검증. python check.py [--model]"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "tools"))
from octest import Sandbox, check, finish, model_check, model_enabled, skill_loaded  # noqa: E402
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fake_llm import FakeLLM  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
SCRIPT = ".opencode/skills/mermaid-diagram/scripts/scan_structure.py"
OUT = HERE / "out" / "architecture.md"


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


tmp = pathlib.Path(tempfile.mkdtemp(prefix="s4b-"))
try:
    shutil.rmtree(HERE / "out", ignore_errors=True)
    h = run(SCRIPT, "--help")
    check("script --help exits 0", h.returncode == 0 and "--out" in h.stdout, h.stderr)

    p = run(SCRIPT, "sample-app", "--out", "out/architecture.md")
    check("script exits 0", p.returncode == 0, p.stderr)
    data = json.loads(p.stdout) if p.returncode == 0 else {}
    check("sample app has 6-8 modules", 6 <= len(data.get("modules", [])) <= 8, str(data.get("modules")))
    check("exactly one import cycle", data.get("cycles") == [[
        "services/notifications.py", "services/orders.py", "services/payments.py", "services/notifications.py"]],
        str(data.get("cycles")))
    check("entry point found", data.get("entry_points") == ["main.py"])
    md = OUT.read_text(encoding="utf-8") if OUT.is_file() else ""
    m = re.search(r"```mermaid\n(.*?)```", md, re.S)
    graph = m.group(1) if m else ""
    check("output has a mermaid block", graph.startswith("flowchart LR"))
    check("mermaid has one edge per import", len(re.findall(r"^\s+m_\S+ -[.]?->", graph, re.M)) == len(data.get("edges", [])) == 13)
    check("cycle edges are highlighted", "linkStyle 6,10,12" in graph)
    check("subgraph is closed", graph.count("subgraph ") == graph.count("\n  end"))
    check("output has a plain-text tree", "```text\nsample-app/" in md and "├── " in md)
    check("output lists the cycle", "services/orders.py -> services/payments.py" in md)

    # lazy imports and relative imports are understood (temporary project, never committed)
    proj = tmp / "proj"
    (proj / "pkg").mkdir(parents=True)
    (proj / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (proj / "pkg" / "a.py").write_text("from . import b\n", encoding="utf-8")
    (proj / "pkg" / "b.py").write_text("def f():\n    from pkg import a\n    return a\n", encoding="utf-8")
    p = run(SCRIPT, proj, "--out", tmp / "o.md")
    d = json.loads(p.stdout)
    edges = {(e["from"], e["to"]): e["lazy"] for e in d["edges"]}
    check("relative import resolved, function-level import marked lazy",
          edges == {("pkg/a.py", "pkg/b.py"): False, ("pkg/b.py", "pkg/a.py"): True}, str(edges))
    check("cycle through a lazy edge is still reported", len(d["cycles"]) == 1)

    p = run(SCRIPT, "no-such-dir")
    check("missing directory exits 2", p.returncode == 2 and "error" in p.stderr, p.stderr)
    (tmp / "broken").mkdir()
    (tmp / "broken" / "x.py").write_text("def (:\n", encoding="utf-8")
    p = run(SCRIPT, tmp / "broken", "--out", tmp / "b.md")
    check("syntax error exits 2 with a message", p.returncode == 2 and "cannot parse" in p.stderr, p.stderr)

    with Sandbox("s4b") as sb:
        skills = sb.debug_skills(cwd=HERE)
        found = [s for s in skills if s["name"] == "mermaid-diagram"]
        check("skill discovered", bool(found))
        check("description has Korean triggers", bool(found) and "아키텍처 다이어그램" in found[0]["description"])
        scripted_skill_run(sb, HERE, 'mermaid-diagram', f"python {(HERE / SCRIPT).as_posix()} sample-app --out out/architecture.md", "cycles", 'mermaid-diagram')
        if model_enabled():
            shutil.rmtree(HERE / "out", ignore_errors=True)
            out = sb.run_model("mermaid-diagram 스킬로 sample-app 의 아키텍처를 다이어그램으로 만들고 구조를 설명해 줘. 순환 import 가 있으면 알려 줘.", cwd=HERE)
            model_check("model loaded the skill", out, skill_loaded(out, "mermaid-diagram"))
            model_check("diagram file generated by the script", out, OUT.is_file() and "scan_structure.py" in out)
            model_check("answer spots the cycle", out, "notifications" in out and "orders" in out and "payments" in out)
finally:
    shutil.rmtree(HERE / "out", ignore_errors=True)
    shutil.rmtree(tmp, ignore_errors=True)

finish()
