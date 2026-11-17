#!/usr/bin/env python3
"""build.py - cargo로 릴리스 빌드를 하고 결과를 bin/glossary-mcp (Windows는 .exe)로 복사한다.

    python build.py              # 빌드 + 복사
    python build.py --offline    # 인터넷 없이, 이미 받아 둔 crates만으로 빌드

종료 코드: 0 성공 / 2 cargo가 없음 / 3 crates를 받을 수 없음(인터넷 없음 + 캐시 없음) / 1 그 밖의 빌드 실패(코드 오류)

--target-dir target 을 명시하는 이유: 어떤 PC는 ~/.cargo/config.toml 에 전역 target-dir 이 지정되어 있어서
(이 예제를 만든 PC가 그렇다) 그냥 빌드하면 결과가 이 폴더의 target/ 이 아닌 곳에 생긴다.
"""
import shutil
import socket
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
NAME = "glossary-mcp"
EXE = NAME + (".exe" if sys.platform == "win32" else "")


def registry_reachable(timeout=3.0):
    """crates 인덱스에 3초 안에 TCP로 닿는지. (cargo는 닿지 않으면 한참 재시도하며 멈춰 있는다)"""
    try:
        with socket.create_connection(("index.crates.io", 443), timeout=timeout):
            return True
    except OSError:
        return False


def main():
    if not shutil.which("cargo"):
        print("cargo를 찾을 수 없다. https://rustup.rs 로 Rust를 설치하면 cargo가 함께 설치된다.")
        return 2
    offline = "--offline" in sys.argv
    if not offline and not registry_reachable():
        print("crates 인덱스(index.crates.io)에 3초 안에 닿지 않아 --offline 으로 빌드한다 (받아 둔 crates가 있어야 한다)")
        offline = True
    cmd = ["cargo", "build", "--release", "--target-dir", "target"] + (["--offline"] if offline else [])
    print("$", " ".join(cmd), flush=True)
    proc = subprocess.run(cmd, cwd=str(HERE))
    if proc.returncode != 0:
        return 3 if offline else 1
    built = HERE / "target" / "release" / EXE
    (HERE / "bin").mkdir(exist_ok=True)
    shutil.copy2(built, HERE / "bin" / EXE)
    print(f"복사: {built.relative_to(HERE)} -> bin/{EXE} ({(HERE / 'bin' / EXE).stat().st_size / 1024:.0f} KiB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
