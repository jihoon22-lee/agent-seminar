"""팀 용어 사전 조회 스크립트 (스킬 방식).

    python lookup.py "ADR"
    python lookup.py "에러 버짓"

glossary.json 은 이 스크립트의 한 칸 위(스킬 폴더)에 있다. 스킬 폴더를 통째로 복사해도 동작하도록
스크립트 위치를 기준으로 찾는다.
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

GLOSSARY = Path(__file__).resolve().parent.parent / "glossary.json"


def main() -> int:
    if len(sys.argv) < 2:
        print("사용법: python lookup.py <용어>")
        return 2
    term = " ".join(sys.argv[1:]).strip()
    glossary = json.loads(GLOSSARY.read_text(encoding="utf-8"))
    for key, meaning in glossary.items():
        if key.lower() == term.lower():
            print(f"{key}: {meaning}")
            return 0
    print(f"'{term}' 는 사전에 없습니다. 등록된 용어: {', '.join(glossary)}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
