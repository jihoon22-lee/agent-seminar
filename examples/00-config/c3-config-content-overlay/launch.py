"""C3: 파일을 건드리지 않고 이번 실행에만 설정을 얹는다 (OPENCODE_CONFIG_CONTENT 덧씌우기).

    python launch.py --print-config        # 덧씌운 설정이 적용된 결과만 확인 (모델 호출 없음)
    python launch.py --run "지금 몇 시야?"  # opencode run 으로 한 번 실행
    python launch.py                       # opencode TUI 를 그대로 띄움
    (-m provider/model 로 모델을 지정할 수 있다. 지정하지 않으면 평소 설정된 모델)

launch.py 가 하는 일은 세 가지뿐이다.
  1. 이미 OPENCODE_CONFIG_CONTENT 가 있으면 읽어서 (JSON 객체여야 함) 그 위에 얹는다.
  2. mcp.clock 과 username 을 더한 JSON 을 만든다.
  3. 그 JSON 을 "자식 프로세스의 환경변수"로만 넘겨 opencode 를 실행한다.
내 셸의 환경변수, ~/.config/opencode, 프로젝트의 opencode.json 은 하나도 바뀌지 않는다.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
OVERLAY_USERNAME = "overlay-user"


def find_opencode() -> str:
    found = os.environ.get("OPENCODE_BIN") or shutil.which("opencode")
    if not found:
        raise SystemExit("opencode 를 찾을 수 없습니다. PATH 를 확인하거나 OPENCODE_BIN 을 지정하세요.")
    return found


def build_overlay(existing: str | None) -> dict[str, Any]:
    """기존 OPENCODE_CONFIG_CONTENT(있다면) 위에 clock MCP 와 username 을 얹는다."""
    overlay: Any = {}
    if existing:
        try:
            overlay = json.loads(existing)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"기존 OPENCODE_CONFIG_CONTENT 가 JSON 이 아닙니다: {exc}")
        if not isinstance(overlay, dict):
            raise SystemExit("기존 OPENCODE_CONFIG_CONTENT 는 JSON 객체여야 합니다.")
    overlay.setdefault("$schema", "https://opencode.ai/config.json")
    overlay["username"] = OVERLAY_USERNAME
    mcp = overlay.setdefault("mcp", {})
    # 덧씌우기 JSON 에는 "설정 파일의 위치"가 없으므로 상대 경로가 실행 위치에 따라 달라진다.
    # 그래서 파이썬 실행 파일과 서버 스크립트를 절대 경로로 적는다.
    mcp["clock"] = {
        "type": "local",
        "command": [sys.executable, str(HERE / "clock_server.py")],
        "enabled": True,
    }
    return overlay


def child_env(overlay: dict[str, Any], cwd: Path) -> dict[str, str]:
    env = dict(os.environ)
    # `opencode run` 은 프로젝트 폴더를 프로세스 cwd 가 아니라 $PWD 에서 가져온다.
    env["PWD"] = str(cwd)
    env["OPENCODE_CONFIG_CONTENT"] = json.dumps(overlay, ensure_ascii=False)
    env["PYTHONUTF8"] = "1"
    return env


def print_config(env: dict[str, str], cwd: Path) -> int:
    """`opencode debug config` 결과에서 덧씌움과 관련된 부분만 보여 준다 (개인 설정 전체는 출력하지 않음)."""
    proc = subprocess.run([find_opencode(), "debug", "config"], cwd=str(cwd), env=env,
                          capture_output=True, stdin=subprocess.DEVNULL, timeout=120)
    text = proc.stdout.decode("utf-8", errors="replace")
    if "{" not in text:
        print(proc.stderr.decode("utf-8", errors="replace"), file=sys.stderr)
        return proc.returncode or 1
    merged = json.loads(text[text.find("{"):])
    project = json.loads((HERE / "opencode.json").read_text(encoding="utf-8"))
    print("프로젝트 opencode.json 의 username :", project["username"])
    print("덧씌운 설정 후 username            :", merged.get("username"))
    print("mcp 항목                           :", ", ".join(merged.get("mcp", {})) or "(없음)")
    print("mcp.clock                          :", json.dumps(merged.get("mcp", {}).get("clock"), ensure_ascii=False))
    print("instructions                       :", merged.get("instructions"))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--print-config", action="store_true", help="덧씌운 결과만 출력하고 끝낸다")
    parser.add_argument("--run", metavar="PROMPT", help="opencode run 으로 프롬프트 하나를 실행한다")
    parser.add_argument("-m", "--model", help="provider/model (생략하면 평소 설정된 모델)")
    parser.add_argument("--dir", default=str(HERE), help="opencode 를 실행할 폴더 (기본: 이 예제 폴더)")
    args = parser.parse_args()

    cwd = Path(args.dir).resolve()
    overlay = build_overlay(os.environ.get("OPENCODE_CONFIG_CONTENT"))
    env = child_env(overlay, cwd)

    if args.print_config:
        return print_config(env, cwd)

    cmd = [find_opencode()]
    if args.run is not None:
        cmd += ["run", "--auto"]
        if args.model:
            cmd += ["-m", args.model]
        cmd.append(args.run)
    elif args.model:
        cmd += ["-m", args.model]
    print(f"[launch] OPENCODE_CONFIG_CONTENT 를 얹어 실행: {' '.join(cmd[:3])} ...", file=sys.stderr)
    try:
        return subprocess.run(cmd, cwd=str(cwd), env=env).returncode
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
