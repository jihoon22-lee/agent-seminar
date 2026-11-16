"""s3b-release-notes 검증. python check.py [--model]"""
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
SANDBOX = HERE / "sandbox"
SCRIPT_REL = ".opencode/skills/release-notes/scripts/release_notes.py"


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
    p = run("prepare.py")
    check("prepare.py runs", p.returncode == 0 and (SANDBOX / ".git").exists(), p.stderr)
    check("sandbox has the skill copied in", (SANDBOX / SCRIPT_REL).is_file()
          and (SANDBOX / ".opencode/skills/release-notes/SKILL.md").is_file())
    tags = subprocess.run(["git", "tag"], cwd=SANDBOX, capture_output=True, text=True).stdout.split()
    check("tag v1.0.0 exists", tags == ["v1.0.0"], str(tags))
    n = subprocess.run(["git", "rev-list", "--count", "v1.0.0..HEAD"], cwd=SANDBOX, capture_output=True, text=True).stdout.strip()
    check("12 commits after the tag", n == "12", n)

    h = run(SCRIPT_REL, "--help", cwd=SANDBOX)
    check("script --help exits 0", h.returncode == 0 and "--from" in h.stdout, h.stderr)

    p = run(SCRIPT_REL, "--from", "v1.0.0", "--to", "HEAD", cwd=SANDBOX)
    md = p.stdout
    check("script exits 0", p.returncode == 0, p.stderr)
    check("breaking section first", md.index("## Breaking changes") < md.index("## Features"), md[:400])
    check("breaking note from commit body", "clients must call /v2/search" in md)
    for heading in ("## Features", "## Bug fixes", "## Performance", "## Refactoring", "## Documentation",
                    "## Tests", "## CI", "## Other (not Conventional Commits)"):
        check(f"section {heading!r}", heading in md)
    check("scope rendered", "**cart**: add coupon code support" in md)
    check("range excludes pre-tag commits", "add product list endpoint" not in md)
    check("commit hash kept", md.count("(`") == 13, str(md.count("(`")))  # 12 commits + breaking listed twice

    j = json.loads(run(SCRIPT_REL, "--from", "v1.0.0", "--format", "json", cwd=SANDBOX).stdout)
    check("--format json works, --to defaults to HEAD", len(j["commits"]) == 12 and j["to"] == "HEAD")
    p = run(SCRIPT_REL, cwd=SANDBOX)
    check("--from defaults to latest tag", p.returncode == 0 and "v1.0.0 -> HEAD" in p.stdout, p.stderr)
    p = run(SCRIPT_REL, "--from", "v9.9.9", cwd=SANDBOX)
    check("unknown tag exits 2", p.returncode == 2 and "error" in p.stderr, p.stderr)
    empty = tempfile.mkdtemp(prefix="s3b-notrepo-")
    try:
        p = run(str(SANDBOX / SCRIPT_REL), "--repo", empty, "--from", "v1.0.0", cwd=empty)
        check("directory that is not a git repo exits 2", p.returncode == 2 and "error" in p.stderr, p.stderr)
    finally:
        shutil.rmtree(empty, ignore_errors=True)

    with Sandbox("s3b") as sb:
        skills = sb.debug_skills(cwd=SANDBOX)
        found = [s for s in skills if s["name"] == "release-notes"]
        check("skill discovered in sandbox", bool(found))
        check("description has Korean triggers", bool(found) and "릴리스 노트" in found[0]["description"])
        scripted_skill_run(sb, SANDBOX, 'release-notes', f"python {(SANDBOX / SCRIPT_REL).as_posix()} --from v1.0.0 --to HEAD", "## Breaking changes", 'release-notes')
        if model_enabled():
            out = sb.run_model("release-notes 스킬을 사용해서 v1.0.0 이후 변경사항으로 사용자용 한국어 릴리스 노트를 써줘", cwd=SANDBOX)
            model_check("model loaded the skill", out, skill_loaded(out, "release-notes"))
            model_check("model ran the bundled script", out, "release_notes.py" in out)
            model_check("answer is Korean and mentions the breaking change", out, "/v2/search" in out and "릴리스" in out)
finally:
    def _onerror(func, path, _exc):
        import os, stat
        os.chmod(path, stat.S_IWRITE)
        func(path)
    shutil.rmtree(SANDBOX, onerror=_onerror)

finish()
