#!/usr/bin/env python3
"""prepare.py - M3 준비: secrets/token.txt (가짜 토큰 파일)을 만든다.

opencode.json의 {file:./secrets/token.txt} 가 이 파일을 읽는다.
이 파일이 없으면 opencode는 이 폴더에서 아예 시작하지 않는다 (설정 오류).
secrets/ 는 .gitignore 대상이다. 여러 번 실행해도 안전하다.

    python prepare.py
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
TOKEN_FILE = HERE / "secrets" / "token.txt"
# 실제 토큰이 아니라 데모용 가짜 값이다. (문자열을 나눠 쓴 것은 토큰 탐지기를 의식한 습관일 뿐)
FAKE_TOKEN = "demo-" + "file-token-456"


def main() -> None:
    TOKEN_FILE.parent.mkdir(exist_ok=True)
    # 끝 줄바꿈이 있어도 opencode는 {file:} 값의 끝 공백/줄바꿈을 잘라 준다.
    TOKEN_FILE.write_text(FAKE_TOKEN + "\n", encoding="utf-8")
    print(f"만들었습니다: {TOKEN_FILE.relative_to(HERE)}  (내용은 가짜 토큰)")
    print("다음: 환경 변수를 정하고 opencode를 실행하세요 (README 참고).")


if __name__ == "__main__":
    main()
