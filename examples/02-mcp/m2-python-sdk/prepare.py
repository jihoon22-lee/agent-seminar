#!/usr/bin/env python3
"""prepare.py - M2 준비: 가상환경(.venv) 만들기 -> `mcp` SDK 설치 -> 이 OS용 opencode.json 만들기.

    python prepare.py                              # Windows (PowerShell)
    python3 prepare.py                             # Linux (python 명령이 없다면)
    python prepare.py --index-url https://미러주소/simple    # 패키지 미러를 쓸 때

왜 opencode.json을 생성하나?
  가상환경 안의 파이썬 경로가 OS마다 다르기 때문이다.
      Windows:  .venv\\Scripts\\python.exe        Linux:  .venv/bin/python
  그래서 템플릿 두 개(opencode.windows.json, opencode.linux.json)를 두고,
  현재 OS에 맞는 쪽을 opencode.json으로 복사한다. (opencode.json은 .gitignore 대상)

여러 번 실행해도 안전하다 (가상환경이 있으면 재사용하고, 패키지는 다시 확인만 한다).
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent


def venv_python(venv_dir: Path) -> Path:
    return venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def run(cmd: list[str]) -> None:
    print("$", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run(cmd, check=True)


def write_config(venv_dir: Path, out: Path) -> None:
    template = HERE / ("opencode.windows.json" if os.name == "nt" else "opencode.linux.json")
    config = json.loads(template.read_text(encoding="utf-8"))
    default_venv = HERE / ".venv"
    if venv_dir.resolve() != default_venv.resolve():
        # 기본 위치가 아닌 곳에 가상환경을 만든 경우(예: check.py) 절대 경로를 쓴다
        for server in config["mcp"].values():
            server["command"][0] = venv_python(venv_dir).as_posix()
    out.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="M2 준비: venv + mcp SDK + opencode.json")
    parser.add_argument("--venv-dir", default=str(HERE / ".venv"), help="가상환경 위치 (기본: .venv)")
    parser.add_argument("--config-out", default=str(HERE / "opencode.json"), help="생성할 opencode.json 경로")
    parser.add_argument("--index-url", help="pip 패키지 미러 주소 (생략하면 pip 기본 설정/환경 변수 PIP_INDEX_URL 사용)")
    args = parser.parse_args()
    venv_dir, config_out = Path(args.venv_dir), Path(args.config_out)

    if not venv_python(venv_dir).exists():
        run([sys.executable, "-m", "venv", str(venv_dir)])
    pip = [str(venv_python(venv_dir)), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(HERE / "requirements.txt")]
    if args.index_url:
        pip += ["--index-url", args.index_url]
    try:
        run(pip)
    except subprocess.CalledProcessError:
        print("\n[실패] pip 설치에 실패했습니다. 인터넷이 막힌 환경이라면 패키지 미러 주소를 지정하세요:")
        print("  python prepare.py --index-url https://<미러 주소>/simple")
        print("  (또는 환경 변수 PIP_INDEX_URL, 혹은 `pip config set global.index-url <주소>`)")
        return 2

    write_config(venv_dir, config_out)
    print(f"\n만들었습니다: {config_out.name}  (가상환경: {venv_dir.name}, 서버: server.py)")
    print("다음: opencode mcp list 로 연결을 확인하고 opencode를 실행하세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
