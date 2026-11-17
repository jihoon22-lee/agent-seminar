"""플러그인용 검사기: 파일을 읽어 문제를 한 줄씩 출력합니다. (표준 라이브러리만)

    python scripts/check_file.py <파일>

종료 코드: 0 = 문제 없음, 1 = 문제 있음(출력에 목록), 그 밖 = 검사기 자체 실패.
(ruff, flake8 같은 실제 린터도 같은 약속을 씁니다: 0 깨끗, 1 발견.)
.py : 문법 오류, 쓰지 않는 import, 100자를 넘는 줄
.json : 문법 오류 (formatter 는 틀린 JSON 을 조용히 건너뛰므로 여기서 알려 줍니다)
"""
import ast
import json
import pathlib
import sys

MAX_LINE = 100


def check_py(text: str) -> list[tuple[int, str]]:
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return [(exc.lineno or 1, f"문법 오류: {exc.msg}")]
    imported: dict[str, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.setdefault((alias.asname or alias.name).split(".")[0], node.lineno)
        elif isinstance(node, ast.ImportFrom) and node.module != "__future__":
            for alias in node.names:
                if alias.name != "*":
                    imported.setdefault(alias.asname or alias.name, node.lineno)
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    found = [(line, f"쓰지 않는 import: {name}") for name, line in imported.items() if name not in used]
    for number, line in enumerate(text.splitlines(), 1):
        if len(line) > MAX_LINE:
            found.append((number, f"{len(line)}자 줄 ({MAX_LINE}자 초과)"))
    return found


def check_json(text: str) -> list[tuple[int, str]]:
    try:
        json.loads(text)
    except ValueError as exc:
        return [(getattr(exc, "lineno", 1), f"JSON 문법 오류: {getattr(exc, 'msg', exc)}")]
    return []


def main() -> int:
    path = pathlib.Path(sys.argv[1])
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix == ".py":
        found = check_py(text)
    elif suffix == ".json":
        found = check_json(text)
    else:
        return 0
    for line, message in sorted(found)[:20]:
        print(f"{line}행: {message}")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
