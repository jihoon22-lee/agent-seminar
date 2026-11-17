"""내장 formatter 용 스크립트: .json 파일을 키 정렬 + 2칸 들여쓰기로 다시 씁니다. (표준 라이브러리만)

    python scripts/fmt_json.py <파일>

opencode 가 write/edit 로 .json 을 고친 직후 `opencode.json` 의 `formatter` 설정으로 실행합니다.
JSON 문법이 틀린 파일은 건드리지 않고 종료 코드 1 로 끝납니다.
"""
import json
import pathlib
import sys


def main() -> int:
    path = pathlib.Path(sys.argv[1])
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"fmt_json: 건너뜀 ({exc})", file=sys.stderr)
        return 1
    text = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
