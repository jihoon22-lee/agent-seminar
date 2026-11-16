"""C4 비교표: 격리 관련 스위치가 실제로 무엇을 숨기는지 한 번에 확인한다 (모델 호출 없음).

    python flags_demo.py

각 줄은 같은 샌드박스에서 `opencode debug config` 와 `opencode debug skill` 을 실행한 결과다.
  username      : 어느 설정 파일의 값이 이겼나 (c4-project-user = 이 폴더의 opencode.json, fake-global-user = 전역, c4-test-user = test-config.json)
  project-skill : .opencode/skills/c4-local-skill 이 보이나
  external-skill: 가짜 홈의 ~/.claude/skills, ~/.agents/skills 스킬이 보이나
  plugin        : .opencode/plugins/c4-marker.js 가 실제로 로드되었나
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import isolated

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent


def make_fake_home(root: Path) -> Path:
    home = root / "fake-home"
    for rel, name in ((".claude/skills", "ext-claude-skill"), (".agents/skills", "ext-agents-skill")):
        skill = home / rel / name
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: 가짜 홈의 외부 스킬 ({name})\n---\n본문 없음\n", encoding="utf-8")
    return home


def run_opencode(args: list[str], env: dict[str, str]) -> str:
    proc = subprocess.run([isolated.find_opencode(), *args], cwd=str(HERE), env=env,
                          capture_output=True, stdin=subprocess.DEVNULL, timeout=180)
    text = proc.stdout.decode("utf-8", errors="replace")
    start = min([i for i in (text.find("{"), text.find("[")) if i != -1], default=-1)
    if start == -1:
        raise SystemExit(f"opencode {' '.join(args)} 실패:\n{proc.stderr.decode('utf-8', errors='replace')[:500]}")
    return text[start:]


def measure(label: str, root: Path, home: Path, flags: list[str], extra: dict[str, str],
            keep_external_skills: bool = False) -> tuple[str, str, str, str, str]:
    sandbox = root / f"sb-{len(list(root.glob('sb-*')))}"
    sandbox.mkdir()
    env = isolated.sandbox_env(sandbox, HERE / "fake-global.json", {})
    env.update(extra)
    env.update({"HOME": str(home), "USERPROFILE": str(home)})  # `~` 을 가짜 홈으로
    if keep_external_skills:
        env.pop("OPENCODE_DISABLE_EXTERNAL_SKILLS", None)
    marker = sandbox / "marker.txt"
    env["C4_MARKER_FILE"] = str(marker)
    username = json.loads(run_opencode([*flags, "debug", "config"], env)).get("username")
    skills = {s["name"] for s in json.loads(run_opencode([*flags, "debug", "skill"], env))}
    return (label, str(username),
            "visible" if "c4-local-skill" in skills else "hidden",
            "visible" if skills & {"ext-claude-skill", "ext-agents-skill"} else "hidden",
            "loaded" if marker.exists() else "not loaded")


def main() -> None:
    test_cfg = str(HERE / "test-config.json")
    rows_spec = [
        ("(none) sandbox only", [], {}, True),
        ("OPENCODE_DISABLE_EXTERNAL_SKILLS=1", [], {}, False),
        ("OPENCODE_DISABLE_PROJECT_CONFIG=1", [], {"OPENCODE_DISABLE_PROJECT_CONFIG": "1"}, True),
        ("--pure", ["--pure"], {}, True),
        ("OPENCODE_CONFIG=test-config.json", [], {"OPENCODE_CONFIG": test_cfg}, True),
        ("DISABLE_PROJECT_CONFIG + CONFIG", [], {"OPENCODE_DISABLE_PROJECT_CONFIG": "1", "OPENCODE_CONFIG": test_cfg}, True),
    ]
    rows = []
    with tempfile.TemporaryDirectory(prefix="c4-flags-") as tmp:
        root = Path(tmp)
        home = make_fake_home(root)
        for label, flags, extra, external in rows_spec:
            rows.append(measure(label, root, home, flags, extra, keep_external_skills=external))
    header = ("setting", "username", "project-skill", "external-skill", "plugin")
    widths = [max(len(r[i]) for r in [header, *rows]) for i in range(5)]
    for row in [header, tuple("-" * w for w in widths), *rows]:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)).rstrip())
    print("\n외부 스킬 열은 가짜 홈에 ~/.claude/skills, ~/.agents/skills 를 만들어 두고 측정했습니다.")
    print("username 이 fake-global-user 이면 전역 설정 값입니다. (샌드박스의 전역 설정 = fake-global.json)")


if __name__ == "__main__":
    main()
