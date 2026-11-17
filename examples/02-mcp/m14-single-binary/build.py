#!/usr/bin/env python3
"""build.py - cargo로 릴리스 빌드를 하고 결과를 bin/glossary-mcp (Windows는 .exe)로 복사한다.

    python build.py              # 빌드 + 복사
    python build.py --offline    # 인터넷 없이, 이미 받아 둔 crates만으로 빌드

기본 동작: 먼저 그냥 빌드한다(cargo 설정의 미러, 받아 둔 캐시가 모두 그대로 쓰인다). 받기 단계에서 실패하면
`--offline` 으로 한 번 더 시도한다. 받기 단계가 오래 멈춰 있지 않도록 CARGO_NET_RETRY=1, CARGO_HTTP_TIMEOUT=15 를
기본값으로 준다(이미 환경 변수로 정해 두었으면 그 값을 쓴다).

종료 코드: 0 성공 / 2 cargo가 없음 / 3 crates를 받을 수 없음(인터넷 없음 + 캐시 없음) / 1 그 밖의 빌드 실패(코드 오류)

--target-dir target 을 명시하는 이유: 어떤 PC는 ~/.cargo/config.toml 에 전역 target-dir 이 지정되어 있어서
(이 예제를 만든 PC가 그렇다) 그냥 빌드하면 결과가 이 폴더의 target/ 이 아닌 곳에 생긴다.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
NAME = "glossary-mcp"
EXE = NAME + (".exe" if sys.platform == "win32" else "")


# cargo 가 받기 단계에서 실패했다는 뜻의 문구들 (컴파일 오류와 구분하는 데 쓴다)
NETWORK_WORDS = ("unable to update registry", "failed to download", "could not resolve host", "couldn't connect", "failed to connect",
                 "spurious network error", "failed to get", "timed out", "connection refused", "network", "download of config.json failed")


def run_cargo(extra):
    """cargo build --release 를 실행해 출력을 그대로 보여 주면서 모아 둔다. 반환: (종료 코드, 출력 전체)."""
    cmd = ["cargo", "build", "--release", "--target-dir", "target"] + extra
    print("$", " ".join(cmd), flush=True)
    # 받기 단계가 오래 멈춰 있지 않게 한다 (cargo 기본값은 재시도 3번 x 30초 단위). 사용자가 직접 정한 값은 존중한다.
    env = dict(os.environ)
    env.setdefault("CARGO_NET_RETRY", "1")
    env.setdefault("CARGO_HTTP_TIMEOUT", "15")
    proc = subprocess.Popen(cmd, cwd=str(HERE), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8", errors="replace")
    lines = []
    for line in proc.stdout:
        print(line, end="", flush=True)
        lines.append(line)
    return proc.wait(), "".join(lines)


def main():
    if not shutil.which("cargo"):
        print("cargo를 찾을 수 없다. https://rustup.rs 로 Rust를 설치하면 cargo가 함께 설치된다.")
        return 2
    if "--offline" in sys.argv:
        code, _ = run_cargo(["--offline"])
        if code != 0:
            return 3
    else:
        # 먼저 평범하게 빌드한다. crates.io 에 직접 닿지 않아도 설정한 미러([source.crates-io] replace-with)나
        # 받아 둔 캐시로 되는 PC가 많기 때문이다. 직접 TCP로 index.crates.io 를 찔러 보고 --offline 을 강제하지 않는다.
        code, output = run_cargo([])
        if code != 0:
            if "could not compile" in output or "error[E" in output:
                return 1  # 받기가 아니라 코드 문제다
            print("\n받기 단계에서 실패해 --offline 으로 한 번 더 시도한다 (받아 둔 crates가 있어야 한다)", flush=True)
            code, _ = run_cargo(["--offline"])
            if code != 0:
                # 오프라인으로도 안 됨: 첫 시도의 원인이 네트워크로 보이면 '받을 수 없음'(3), 아니면 그 밖의 실패(1)
                return 3 if any(w in output.lower() for w in NETWORK_WORDS) else 1
    built = HERE / "target" / "release" / EXE
    (HERE / "bin").mkdir(exist_ok=True)
    shutil.copy2(built, HERE / "bin" / EXE)
    print(f"복사: {built.relative_to(HERE)} -> bin/{EXE} ({(HERE / 'bin' / EXE).stat().st_size / 1024:.0f} KiB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
