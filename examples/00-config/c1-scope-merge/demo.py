"""C1 설정 병합 데모: 다섯 가지 상황에서 `opencode debug config`의 병합 결과를 표로 보여 준다.

    python demo.py            # 다섯 시나리오를 차례로 실행하고 표를 출력
    python demo.py --json     # 마지막 시나리오의 병합 결과 전체를 JSON으로 출력

실제 ~/.config/opencode 는 건드리지 않는다. global-config/opencode.json 을
임시 XDG_CONFIG_HOME 으로 복사해 "전역 설정" 대역으로 쓴다. 표준 라이브러리만 사용.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent

# 시나리오 5에서 OPENCODE_CONFIG_CONTENT 로 주입하는 JSON (파일이 아니라 환경변수)
CONTENT = {
    "username": "content-user",
    "instructions": ["content-rules.md"],
    "mcp": {"layer-content": {"type": "local", "command": ["python", "content.py"], "enabled": False}},
    "permission": {"bash": {"git status*": "deny"}},
}

# 낮은 우선순위 -> 높은 우선순위
LAYERS = [
    ("global", "전역 (XDG_CONFIG_HOME/opencode/opencode.json)"),
    ("OPENCODE_CONFIG", "OPENCODE_CONFIG 가 가리키는 파일 (team-defaults.json)"),
    ("project", "프로젝트 루트 opencode.json"),
    (".opencode", ".opencode/opencode.json"),
    ("CONFIG_CONTENT", "OPENCODE_CONFIG_CONTENT 환경변수"),
]

SHOWN_KEYS = ("username", "share", "instructions", "mcp", "permission")


def find_opencode() -> str:
    found = os.environ.get("OPENCODE_BIN") or shutil.which("opencode")
    if not found:
        raise SystemExit("opencode 를 찾을 수 없습니다. PATH 를 확인하거나 OPENCODE_BIN 을 지정하세요.")
    return found


def load_layer_sources() -> dict[str, dict[str, Any]]:
    def read(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    return {
        "global": read(HERE / "global-config" / "opencode.json"),
        "OPENCODE_CONFIG": read(HERE / "team-defaults.json"),
        "project": read(HERE / "opencode.json"),
        ".opencode": read(HERE / ".opencode" / "opencode.json"),
        "CONFIG_CONTENT": CONTENT,
    }


def flatten(node: Any, prefix: str = "") -> dict[str, Any]:
    """병합 결과를 '경로 -> 값' 으로 펼친다. 배열은 항목별로, mcp.<이름> 은 항목 하나로 본다."""
    out: dict[str, Any] = {}
    if isinstance(node, dict):
        for key, value in node.items():
            path = f"{prefix}.{key}" if prefix else key
            if prefix == "mcp":
                out[path] = value
            else:
                out.update(flatten(value, path))
    elif isinstance(node, list):
        for item in node:
            out[f"{prefix}[{json.dumps(item, ensure_ascii=False)}]"] = item
    else:
        out[prefix] = node
    return out


def summarize(value: Any) -> str:
    if isinstance(value, dict) and "command" in value:  # mcp 항목
        return f"{value.get('type')} {' '.join(value['command'])} (enabled={str(value.get('enabled')).lower()})"
    return json.dumps(value, ensure_ascii=False)


def run_debug_config(cwd: Path, env: dict[str, str]) -> dict[str, Any]:
    proc = subprocess.run(
        [find_opencode(), "debug", "config"], cwd=str(cwd), env=env,
        capture_output=True, stdin=subprocess.DEVNULL, timeout=120,
    )
    text = proc.stdout.decode("utf-8", errors="replace")
    start = text.find("{")
    if start == -1:
        raise SystemExit(f"debug config 실패:\n{proc.stderr.decode('utf-8', errors='replace')[:500]}")
    return json.loads(text[start:])


def make_project(tmp: Path, name: str, with_dot_opencode: bool) -> Path:
    """예제 파일을 임시 프로젝트로 복사한다. 시나리오 3 은 .opencode/ 없이, 4 부터는 있는 상태."""
    project = tmp / name
    project.mkdir()
    shutil.copyfile(HERE / "opencode.json", project / "opencode.json")
    if with_dot_opencode:
        (project / ".opencode").mkdir()
        shutil.copyfile(HERE / ".opencode" / "opencode.json", project / ".opencode" / "opencode.json")
    return project


def scenarios(tmp: Path) -> list[tuple[str, Path, dict[str, str], int]]:
    """(설명, 실행 위치, 추가 환경변수, 활성 레이어 수)"""
    empty = tmp / "empty-cwd"  # 프로젝트 설정이 없는 빈 폴더
    empty.mkdir()
    only_root = make_project(tmp, "project-root-only", with_dot_opencode=False)
    full = make_project(tmp, "project-full", with_dot_opencode=True)
    team = str(HERE / "team-defaults.json")
    content = json.dumps(CONTENT)
    return [
        ("1. 전역 설정만 (프로젝트 밖 빈 폴더에서 실행)", empty, {}, 1),
        ("2. + OPENCODE_CONFIG=team-defaults.json", empty, {"OPENCODE_CONFIG": team}, 2),
        ("3. + 프로젝트 루트 opencode.json", only_root, {"OPENCODE_CONFIG": team}, 3),
        ("4. + .opencode/opencode.json", full, {"OPENCODE_CONFIG": team}, 4),
        ("5. + OPENCODE_CONFIG_CONTENT", full, {"OPENCODE_CONFIG": team, "OPENCODE_CONFIG_CONTENT": content}, 5),
    ]


def sandbox_env(tmp: Path) -> dict[str, str]:
    config_home = tmp / "config"
    (config_home / "opencode").mkdir(parents=True)
    shutil.copyfile(HERE / "global-config" / "opencode.json", config_home / "opencode" / "opencode.json")
    env = dict(os.environ)
    for key in ("OPENCODE_CONFIG", "OPENCODE_CONFIG_CONTENT", "OPENCODE_CONFIG_DIR"):
        env.pop(key, None)
    env.update({
        "XDG_CONFIG_HOME": str(config_home),
        "XDG_DATA_HOME": str(tmp / "data"),
        "XDG_CACHE_HOME": str(tmp / "cache"),
        "XDG_STATE_HOME": str(tmp / "state"),
        "OPENCODE_DISABLE_AUTOUPDATE": "1",
        "OPENCODE_DISABLE_EXTERNAL_SKILLS": "1",
        "PYTHONUTF8": "1",
    })
    return env


def attribute(path: str, value: Any, active: list[str], sources: dict[str, dict[str, Any]]) -> tuple[str, bool]:
    """이 항목을 마지막으로(스칼라) 또는 처음으로(배열 항목) 정의한 레이어와, 값이 실제와 일치하는지."""
    is_item = path.endswith("]")
    candidates = []
    for name in active:
        flat = flatten(sources[name])
        if path in flat and flat[path] == value:
            candidates.append(name)
    if not candidates:
        return "?", False
    return (candidates[0] if is_item else candidates[-1]), True


def show_table(title: str, merged: dict[str, Any], active: list[str], sources: dict[str, dict[str, Any]]) -> list[tuple[str, str, str]]:
    print(f"\n=== {title}")
    print(f"    활성 레이어: {' < '.join(active)}")
    rows = []
    shown = {k: merged[k] for k in SHOWN_KEYS if k in merged}
    for path, value in flatten(shown).items():
        layer, ok = attribute(path, value, active, sources)
        shown_path = path.split("[", 1)[0] + "[]" if path.endswith("]") else path
        rows.append((shown_path, summarize(value).strip('"') if isinstance(value, str) else summarize(value), layer if ok else "?"))
    width = max(len(r[0]) for r in rows)
    vwidth = min(max(len(r[1]) for r in rows), 58)
    print(f"    {'키'.ljust(width)}  {'결과 값'.ljust(vwidth)}  이긴 레이어")
    print(f"    {'-' * width}  {'-' * vwidth}  -----------")
    for path, value, layer in rows:
        print(f"    {path.ljust(width)}  {value.ljust(vwidth)}  {layer}")
    return rows


def main() -> None:
    sources = load_layer_sources()
    names = [name for name, _ in LAYERS]
    print("우선순위 (낮음 -> 높음):")
    for i, (name, desc) in enumerate(LAYERS, 1):
        print(f"  {i}. {name:<15} {desc}")
    last: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="c1-scope-merge-") as tmpname:
        tmp = Path(tmpname)
        env = sandbox_env(tmp)
        for title, cwd, extra, count in scenarios(tmp):
            last = run_debug_config(cwd, {**env, **extra})
            show_table(title, last, names[:count], sources)
            last_cwd, last_env = cwd, {**env, **extra}
        # 하위 폴더에서 실행해도 같은 결과인가?
        sub = last_cwd / "src" / "deep"
        sub.mkdir(parents=True)
        same = run_debug_config(sub, last_env) == last
        print(f"\n보너스: 프로젝트의 하위 폴더({sub.relative_to(last_cwd).as_posix()})에서 실행해도 5번과 같은 결과인가? -> {'예' if same else '아니오'}")
    print("\n읽는 법: 스칼라(username, share)는 가장 높은 레이어가 이기고,")
    print("배열(instructions)은 낮은 레이어부터 이어 붙고(중복 제거), 객체(mcp, permission)는 키 단위로 합쳐집니다.")
    if "--json" in sys.argv:
        print(json.dumps(last, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
