"""C1 검사: 설정 레이어 병합 규칙을 `opencode debug config` 로 확인한다 (모델 호출 없음)."""
import json
import subprocess
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "tools"))
from octest import Sandbox, check, finish  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
TEAM = HERE / "team-defaults.json"
CONTENT = json.dumps({
    "username": "content-user",
    "instructions": ["content-rules.md"],
    "permission": {"bash": {"git status*": "deny"}},
})

# 1. 파일이 올바른 JSON 이고 model 키가 없다
for rel in ("global-config/opencode.json", "team-defaults.json", "opencode.json", ".opencode/opencode.json"):
    try:
        data = json.loads((HERE / rel).read_text(encoding="utf-8"))
        check(f"{rel}: JSON 이고 model 키 없음", "model" not in data and "$schema" in data)
    except Exception as exc:  # noqa: BLE001
        check(f"{rel}: JSON 파싱", False, str(exc))

global_cfg = json.loads((HERE / "global-config" / "opencode.json").read_text(encoding="utf-8"))

with Sandbox("c1", global_config=global_cfg) as sb:
    empty = sb.root / "empty-cwd"
    empty.mkdir()

    # 2. 전역만 / + OPENCODE_CONFIG
    cfg = sb.debug_config(empty)
    check("전역만: username=global-user", cfg.get("username") == "global-user", str(cfg.get("username")))
    cfg = sb.debug_config(empty, extra_env={"OPENCODE_CONFIG": str(TEAM)})
    check("OPENCODE_CONFIG 가 전역을 덮어씀: username=team-user", cfg.get("username") == "team-user")
    check("스칼라: share=manual (전역 disabled 를 team 이 덮어씀)", cfg.get("share") == "manual")
    check("배열 이어 붙임 + 중복 제거",
          cfg["instructions"] == ["global-rules.md", "shared-rules.md", "team-rules.md"], str(cfg["instructions"]))
    check("객체 깊은 병합: mcp 두 레이어 모두 존재", {"layer-global", "layer-team"} <= set(cfg["mcp"]))
    check("객체 깊은 병합: permission.bash 규칙 합침",
          cfg["permission"]["bash"] == {"*": "ask", "git status*": "allow"}, str(cfg["permission"]))

    # 3. 프로젝트 + .opencode (이 예제 폴더에서 실행)
    cfg = sb.debug_config(HERE, extra_env={"OPENCODE_CONFIG": str(TEAM)})
    check(".opencode/opencode.json 이 프로젝트 루트 opencode.json 보다 우선: username=dotopencode-user",
          cfg.get("username") == "dotopencode-user", str(cfg.get("username")))
    check("instructions 4개가 낮은 레이어 순서대로",
          cfg["instructions"] == ["global-rules.md", "shared-rules.md", "team-rules.md", "project-rules.md"],
          str(cfg["instructions"]))
    check("mcp 4개 레이어 모두 병합",
          {"layer-global", "layer-team", "layer-project", "layer-dotopencode"} <= set(cfg["mcp"]))
    check("mcp 항목은 enabled=false 로 실제 실행되지 않음", all(v.get("enabled") is False for v in cfg["mcp"].values()))
    check("permission: 서로 다른 레이어의 bash 규칙이 한 객체로, 키 순서 유지",
          list(cfg["permission"]["bash"].items()) == [("*", "ask"), ("git status*", "allow"), ("rm *", "deny")],
          str(cfg["permission"]))
    check("permission.edit: .opencode 가 이김", cfg["permission"]["edit"] == "deny")

    # 4. CONFIG_CONTENT 가 최상위
    env = {"OPENCODE_CONFIG": str(TEAM), "OPENCODE_CONFIG_CONTENT": CONTENT}
    cfg = sb.debug_config(HERE, extra_env=env)
    check("OPENCODE_CONFIG_CONTENT 가 최우선: username=content-user", cfg.get("username") == "content-user")
    check("CONTENT 의 instructions 는 맨 뒤에 추가", cfg["instructions"][-1] == "content-rules.md", str(cfg["instructions"]))
    check("CONTENT 가 같은 키만 덮어씀: git status*=deny, rm *=deny 유지",
          cfg["permission"]["bash"]["git status*"] == "deny" and cfg["permission"]["bash"]["rm *"] == "deny")

    # 5. 하위 폴더에서 실행해도 같은 결과
    sub = sb.root / "proj" / "src" / "deep"
    sub.mkdir(parents=True)
    (sb.root / "proj" / "opencode.json").write_text('{"username": "from-root"}', encoding="utf-8")
    cfg = sb.debug_config(sub)
    check("하위 폴더에서도 상위 폴더의 opencode.json 을 찾음", cfg.get("username") == "from-root", str(cfg.get("username")))

    # 5b. git 저장소 안에서는 저장소 루트까지만 올라간다
    outer = sb.root / "outer"
    (outer / "repo" / "sub").mkdir(parents=True)
    (outer / "opencode.json").write_text('{"username": "above-git-root"}', encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=str(outer / "repo"), check=True, capture_output=True, stdin=subprocess.DEVNULL)
    cfg = sb.debug_config(outer / "repo" / "sub")
    check("git 저장소 안: 저장소 루트 위쪽의 opencode.json 은 읽지 않음", cfg.get("username") == "global-user", str(cfg.get("username")))
    nogit = sb.root / "nogit" / "sub"
    nogit.mkdir(parents=True)
    (sb.root / "nogit" / "opencode.json").write_text('{"username": "parent-of-non-git"}', encoding="utf-8")
    cfg = sb.debug_config(nogit)
    check("git 저장소가 아니면 위쪽 폴더의 opencode.json 도 읽음", cfg.get("username") == "parent-of-non-git", str(cfg.get("username")))

    # 6. 객체를 문자열로 바꾸면 통째로 교체됨
    (sb.root / "proj" / "opencode.json").write_text('{"permission": {"bash": "allow"}}', encoding="utf-8")
    cfg = sb.debug_config(sub)
    check("permission.bash: 객체 -> 문자열이면 교체 (병합 아님)", cfg["permission"]["bash"] == "allow", str(cfg["permission"]))

# 7. demo.py 가 끝까지 돌고 모든 줄의 '이긴 레이어'를 설명할 수 있다
proc = subprocess.run([sys.executable, str(HERE / "demo.py")], capture_output=True, timeout=300,
                      env={**__import__("os").environ, "PYTHONUTF8": "1"})
out = proc.stdout.decode("utf-8", errors="replace")
check("demo.py 정상 종료", proc.returncode == 0, proc.stderr.decode("utf-8", errors="replace")[-500:])
check("demo.py: 다섯 시나리오 출력", all(f"=== {n}." in out for n in "12345"))
check("demo.py: 모든 항목의 레이어가 파일과 일치 (? 없음)", "  ?" not in out and " ?\n" not in out, out[-400:])
check("demo.py: 하위 폴더 보너스 '예'", "-> 예" in out)
finish()
