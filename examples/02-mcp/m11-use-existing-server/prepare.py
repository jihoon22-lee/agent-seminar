#!/usr/bin/env python3
"""prepare.py - M11 준비: 파일 서버가 다룰 연습용 폴더 sandbox/ 를 만든다 (인터넷 필요 없음).

    python prepare.py          # Windows (PowerShell)
    python3 prepare.py         # Linux (python 명령이 없다면)

sandbox/ 는 opencode.json 의 서버 인자 "sandbox" 가 가리키는 폴더다. 이 안의 파일만 서버가 읽을 수 있다.
여러 번 실행해도 안전하다 (같은 내용으로 덮어쓴다).
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
SANDBOX = HERE / "sandbox"

FILES = {
    "README.txt": "연습용 폴더입니다. 파일 서버는 이 폴더 밖을 읽지 못합니다.\n",
    "notes/meeting-2026-11-10.md": (
        "# 주간 회의 (11/10)\n\n"
        "- 결정: 배포는 카나리 5%로 시작한다.\n"
        "- 담당: 로그 수집 점검은 다음 주 화요일까지.\n"
        "- 미정: 장애 보고서 양식 (다음 회의에서 논의)\n"
    ),
    "notes/todo.txt": "1. 용어집에 SLO 예시 추가\n2. 배포 체크리스트 검토\n3. 장애 보고서 양식 초안\n",
    "data/members.csv": "name,role\nA,backend\nB,frontend\nC,ops\n",
}


def main() -> int:
    for rel, text in FILES.items():
        path = SANDBOX / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    print(f"만들었습니다: {SANDBOX} (파일 {len(FILES)}개)")
    print("다음: python show_tools.py 로 서버가 내놓는 도구를 먼저 살펴보세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
