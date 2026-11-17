"""C8 준비: 실험용 sandbox/ 를 만든다. 다시 실행해도 안전하다 (sandbox 를 지우고 새로 만든다).

    python prepare.py                (Linux 에서 python 이 없으면 python3 prepare.py)
    python prepare.py 대상폴더        (check.py 가 임시 폴더에 만들 때 사용)

sandbox/ 는 **자체 git 저장소**다. docs 에이전트의 `docs/**` 규칙은 git 저장소 루트를 기준으로 한 상대 경로이기 때문이다.
(git 저장소가 아닌 폴더에서는 같은 규칙이 docs/guide.md 도 거부했다. 이 저장소 안의 예제 폴더에서 바로 실행해도
루트가 세미나 저장소가 되어 경로가 어긋난다.)

  sandbox/.opencode/agent/   reviewer.md, researcher.md  (예제 폴더에서 복사)
  sandbox/opencode.json      docs 에이전트 정의 (예제 폴더에서 복사)
  sandbox/docs/guide.md      docs 에이전트가 고쳐도 되는 문서
  sandbox/src/calc.py        docs 에이전트가 고치면 안 되는 코드
"""
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _force_remove(func, path, _exc):
    os.chmod(path, stat.S_IWRITE)  # Windows: .git 안의 읽기 전용 파일
    func(path)


def build(dest: Path) -> Path:
    dest = Path(dest)
    if dest.exists():
        shutil.rmtree(dest, onerror=_force_remove)
    (dest / "docs").mkdir(parents=True)
    (dest / "src").mkdir()
    shutil.copytree(HERE / ".opencode", dest / ".opencode",
                    ignore=shutil.ignore_patterns("node_modules", "package.json", "package-lock.json", "bun.lock", ".gitignore"))
    shutil.copyfile(HERE / "opencode.json", dest / "opencode.json")
    (dest / ".gitignore").write_text(".opencode/node_modules/\n.opencode/package.json\n.opencode/bun.lock\n__pycache__/\n",
                                     encoding="utf-8", newline="\n")
    (dest / "docs" / "guide.md").write_text("# 사용법\n\n처음 쓰는 사람을 위한 안내입니다.\n", encoding="utf-8", newline="\n")
    (dest / "src" / "calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8", newline="\n")

    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=dest, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       stdin=subprocess.DEVNULL)

    git("-c", "init.defaultBranch=main", "init")
    git("config", "user.name", "Demo User")
    git("config", "user.email", "demo.invalid")
    git("config", "commit.gpgsign", "false")
    git("add", ".")
    git("commit", "-m", "c8 sandbox")
    return dest


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    target = build(Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "sandbox")
    print(f"만들었습니다: {target}")
    print("  PowerShell:  cd sandbox; opencode --agent docs")
    print("  Linux bash:  cd sandbox && opencode --agent docs")
