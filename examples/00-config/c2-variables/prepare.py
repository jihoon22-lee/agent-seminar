"""C2 준비: secrets/token.txt 에 가짜 토큰 파일을 만든다 (gitignore 대상, 다시 실행해도 안전).

    python prepare.py

토큰은 진짜가 아니라 데모용 문자열이다. 실제 비밀 값을 이 폴더에 넣지 마세요.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
FAKE_FILE_TOKEN = "demo-" + "file-token-" + "456"


def main() -> None:
    secrets = HERE / "secrets"
    secrets.mkdir(exist_ok=True)
    token_file = secrets / "token.txt"
    # 파일 끝의 줄바꿈은 {file:...} 치환 때 제거된다. 에디터가 붙이는 줄바꿈과 같은 상황을 흉내 낸다.
    token_file.write_text(FAKE_FILE_TOKEN + "\n", encoding="utf-8")
    out = HERE / "out"
    if out.exists():
        for old in out.glob("*.json"):
            old.unlink()
    print(f"만들었습니다: {token_file.relative_to(HERE)} (가짜 토큰, git 에 올라가지 않습니다)")
    print()
    print("이제 환경변수를 정하고 실행하세요.")
    print("  PowerShell:")
    print('    $env:DEMO_API_TOKEN = "demo-env-token-123"; $env:DEMO_GREETING = "안녕"; $env:DEMO_NAME = "세미나"')
    print("    opencode debug config")
    print("  Linux bash:")
    print('    export DEMO_API_TOKEN=demo-env-token-123 DEMO_GREETING=안녕 DEMO_NAME=세미나')
    print("    opencode debug config")


if __name__ == "__main__":
    main()
