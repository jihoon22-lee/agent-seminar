"""s2a 실습용 작은 프로젝트(sandbox/)를 만든다.

sandbox/ 는 git 저장소이고
  - 커밋 1개: 할 일 목록 모듈 (complete() 에 한 칸 어긋나는 버그가 있다)
  - 아직 커밋하지 않은 변경: 버그 수정 + 회귀 테스트
가 들어 있으며, 이 예제의 .opencode/ 가 복사되어 있다.

    python prepare.py          (Linux 에서 python 이 없으면 python3 prepare.py)
    cd sandbox && opencode     > 이 변경 작업을 workthrough로 기록해줘
"""
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
SANDBOX = HERE / "sandbox"

STORE_BEFORE = '''"""할 일 목록 저장소."""


class TodoStore:
    def __init__(self):
        self._items = []

    def add(self, title: str) -> int:
        """할 일을 추가하고 1부터 시작하는 번호를 돌려준다."""
        self._items.append({"title": title, "done": False})
        return len(self._items)

    def complete(self, number: int) -> None:
        """add() 가 돌려준 번호의 할 일을 완료 처리한다."""
        self._items[number]["done"] = True

    def pending(self) -> list:
        """아직 끝나지 않은 할 일의 제목 목록."""
        return [item["title"] for item in self._items if not item["done"]]
'''

STORE_AFTER = '''"""할 일 목록 저장소."""


class TodoStore:
    def __init__(self):
        self._items = []

    def add(self, title: str) -> int:
        """할 일을 추가하고 1부터 시작하는 번호를 돌려준다."""
        self._items.append({"title": title, "done": False})
        return len(self._items)

    def complete(self, number: int) -> None:
        """add() 가 돌려준 번호의 할 일을 완료 처리한다."""
        if not 1 <= number <= len(self._items):
            raise IndexError(f"없는 번호입니다: {number}")
        self._items[number - 1]["done"] = True

    def pending(self) -> list:
        """아직 끝나지 않은 할 일의 제목 목록."""
        return [item["title"] for item in self._items if not item["done"]]
'''

TEST_BEFORE = '''import unittest

from todo.store import TodoStore


class TodoStoreTest(unittest.TestCase):
    def test_add_returns_one_based_number(self):
        store = TodoStore()
        self.assertEqual(store.add("우유 사기"), 1)
        self.assertEqual(store.add("빨래"), 2)

    def test_pending_lists_titles(self):
        store = TodoStore()
        store.add("우유 사기")
        self.assertEqual(store.pending(), ["우유 사기"])


if __name__ == "__main__":
    unittest.main()
'''

TEST_AFTER = TEST_BEFORE.replace('''

if __name__ == "__main__":''', '''
    def test_complete_marks_the_given_number(self):
        store = TodoStore()
        store.add("우유 사기")
        store.add("빨래")
        store.complete(1)
        self.assertEqual(store.pending(), ["빨래"])

    def test_complete_last_item(self):
        store = TodoStore()
        store.add("우유 사기")
        store.complete(1)
        self.assertEqual(store.pending(), [])

    def test_complete_unknown_number_raises(self):
        store = TodoStore()
        store.add("우유 사기")
        with self.assertRaises(IndexError):
            store.complete(2)


if __name__ == "__main__":''')


def _force_remove(func, path, _exc):
    # Windows 는 .git 안의 읽기 전용 파일을 그냥 지우지 못한다.
    os.chmod(path, stat.S_IWRITE)
    func(path)


def git(*args: str) -> None:
    subprocess.run(["git", *args], cwd=SANDBOX, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def write(rel: str, text: str) -> None:
    (SANDBOX / rel).write_text(text, encoding="utf-8", newline="\n")


def main() -> None:
    if SANDBOX.exists():
        shutil.rmtree(SANDBOX, onerror=_force_remove)
    (SANDBOX / "todo").mkdir(parents=True)
    (SANDBOX / "tests").mkdir()

    git("-c", "init.defaultBranch=main", "init")
    git("config", "user.name", "Demo User")
    git("config", "user.email", "demo@example.com")
    git("config", "commit.gpgsign", "false")
    git("config", "core.autocrlf", "false")

    # 스킬과 .gitignore 는 처음부터 저장소의 일부로 커밋해 둔다 (작업 변경과 섞이지 않게)
    shutil.copytree(HERE / ".opencode", SANDBOX / ".opencode",
                    ignore=shutil.ignore_patterns("node_modules", "package.json", "package-lock.json",
                                                  "bun.lock", ".gitignore"))
    # 생성되는 기록 문서는 샘플 저장소에서도 git 에 올리지 않는다.
    (SANDBOX / ".gitignore").write_text("workthrough/\n__pycache__/\n.opencode/node_modules/\n",
                                        encoding="utf-8", newline="\n")

    write("todo/__init__.py", "")
    write("todo/store.py", STORE_BEFORE)
    write("tests/__init__.py", "")
    write("tests/test_store.py", TEST_BEFORE)
    git("add", ".")
    git("commit", "-m", "feat(todo): 할 일 저장소 추가")

    # 커밋하지 않은 변경: 버그 수정 + 회귀 테스트
    write("todo/store.py", STORE_AFTER)
    write("tests/test_store.py", TEST_AFTER)

    print(f"sandbox 준비 완료: {SANDBOX}")
    print("다음 단계:")
    print("  cd sandbox")
    print("  opencode")
    print("  > 이 변경 작업을 workthrough로 기록해줘")


if __name__ == "__main__":
    main()
