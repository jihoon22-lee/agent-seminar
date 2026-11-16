"""C4: opencode 를 "일회용 샌드박스"에서 실행한다. 내 실제 설정·세션·로그는 읽지도 쓰지도 않는다.

    python isolated.py debug paths
    python isolated.py debug config
    python isolated.py --global-config my-global.json debug config
    python isolated.py --env OPENCODE_DISABLE_PROJECT_CONFIG=1 debug config
    python isolated.py --keep run "안녕"            # 끝난 뒤 샌드박스 폴더를 지우지 않고 경로를 알려 줌
    python isolated.py                             # 인자가 없으면 TUI (격리된 상태로)

옵션은 opencode 인자보다 앞에 둔다. (--keep, --global-config FILE, --cwd DIR, --env NAME=VALUE)
첫 번째 낯선 인자부터는 전부 opencode 로 그대로 넘어간다. 그 인자가 `--pure` 같은
opencode 옵션이면 앞에 `--` 를 붙여 구분한다:  python isolated.py -- --pure debug config

무엇을 격리하나
  * XDG_CONFIG_HOME / XDG_DATA_HOME / XDG_CACHE_HOME / XDG_STATE_HOME 를 임시 폴더로 바꾼다.
    (전역 opencode.json, 로그인 정보 auth.json, 세션 DB, 캐시가 전부 여기로 간다)
  * OPENCODE_DISABLE_EXTERNAL_SKILLS=1 로 ~/.claude/skills, ~/.agents/skills 를 숨긴다.
  * OPENCODE_CONFIG / OPENCODE_CONFIG_CONTENT / OPENCODE_CONFIG_DIR 는 지운다.
  * TMPDIR / TEMP / TMP 도 임시 폴더로 바꾼다. (opencode 의 임시 파일 위치)
  * 자동 업데이트를 끈다.
표준 라이브러리만 사용하며 Windows, Linux 에서 같게 동작한다.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    _stream.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
DEFAULT_GLOBAL = {"$schema": "https://opencode.ai/config.json", "autoupdate": False}


def find_opencode() -> str:
    found = os.environ.get("OPENCODE_BIN") or shutil.which("opencode")
    if not found:
        raise SystemExit("opencode 를 찾을 수 없습니다. PATH 를 확인하거나 OPENCODE_BIN 을 지정하세요.")
    return found


def sandbox_env(root: Path, global_config: Path | None, extra: dict[str, str]) -> dict[str, str]:
    """root 아래에 격리용 폴더를 만들고, opencode 에 줄 환경변수를 돌려준다."""
    config_home = root / "config"
    (config_home / "opencode").mkdir(parents=True)
    target = config_home / "opencode" / "opencode.json"
    if global_config is not None:
        shutil.copyfile(global_config, target)  # 읽기만 하고 원본은 건드리지 않는다
    else:
        target.write_text(json.dumps(DEFAULT_GLOBAL, indent=2), encoding="utf-8")

    tmp_dir = root / "tmp"
    tmp_dir.mkdir()
    env = dict(os.environ)
    for name in ("OPENCODE_CONFIG", "OPENCODE_CONFIG_CONTENT", "OPENCODE_CONFIG_DIR"):
        env.pop(name, None)
    env.update({
        "XDG_CONFIG_HOME": str(config_home),
        "XDG_DATA_HOME": str(root / "data"),
        "XDG_CACHE_HOME": str(root / "cache"),
        "XDG_STATE_HOME": str(root / "state"),
        "OPENCODE_DISABLE_AUTOUPDATE": "1",
        "OPENCODE_DISABLE_EXTERNAL_SKILLS": "1",
        "PYTHONUTF8": "1",
        # `debug paths` 의 tmp 항목(기본 /tmp/opencode, Windows 는 %TEMP%\opencode)까지 격리한다.
        "TMPDIR": str(tmp_dir),
        "TEMP": str(tmp_dir),
        "TMP": str(tmp_dir),
    })
    if os.name != "nt" and shutil.which("python") is None:
        # Linux 에는 `python3` 만 있는 경우가 많다. MCP 설정이 "python" 을 부르므로 심볼릭 링크를 둔다.
        shim = root / "bin"
        shim.mkdir()
        (shim / "python").symlink_to(sys.executable)
        env["PATH"] = str(shim) + os.pathsep + env.get("PATH", "")
    env.update(extra)
    return env


def parse_args(argv: list[str]) -> tuple[dict, list[str]]:
    opts: dict = {"keep": False, "global_config": None, "cwd": Path.cwd(), "env": {}}
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--":
            i += 1
            break
        if arg in ("-h", "--help"):
            print(__doc__)
            raise SystemExit(0)
        if arg == "--keep":
            opts["keep"] = True
        elif arg in ("--global-config", "--cwd", "--env"):
            if i + 1 >= len(argv):
                raise SystemExit(f"{arg} 에는 값이 필요합니다.")
            value = argv[i + 1]
            i += 1
            if arg == "--global-config":
                opts["global_config"] = Path(value).resolve()
            elif arg == "--cwd":
                opts["cwd"] = Path(value).resolve()
            else:
                name, sep, val = value.partition("=")
                if not sep:
                    raise SystemExit("--env 는 NAME=VALUE 형식이어야 합니다.")
                opts["env"][name] = val
        else:
            break
        i += 1
    return opts, argv[i:]


def main() -> int:
    opts, opencode_args = parse_args(sys.argv[1:])
    if opts["global_config"] is not None and not opts["global_config"].is_file():
        raise SystemExit(f"--global-config 파일이 없습니다: {opts['global_config']}")
    root = Path(tempfile.mkdtemp(prefix="isolated-opencode-"))
    try:
        env = sandbox_env(root, opts["global_config"], opts["env"])
        env["PWD"] = str(opts["cwd"])  # `opencode run` 은 프로젝트 폴더를 $PWD 에서 가져온다
        print(f"[isolated] 샌드박스: {root}  (cwd: {opts['cwd']})", file=sys.stderr)
        try:
            return subprocess.run([find_opencode(), *opencode_args], cwd=str(opts["cwd"]), env=env).returncode
        except KeyboardInterrupt:
            return 130
    finally:
        if opts["keep"]:
            print(f"[isolated] --keep: 남겨 둔 샌드박스 {root}", file=sys.stderr)
        else:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
