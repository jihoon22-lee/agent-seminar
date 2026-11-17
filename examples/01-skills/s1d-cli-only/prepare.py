"""s1d 실습용 git 저장소(sandbox/)를 만든다. 여러 번 실행해도 매번 처음부터 다시 만든다.

    python prepare.py          (Linux 에서 python 이 없으면 python3 prepare.py)
    python prepare.py 대상폴더  (check.py 가 임시 폴더에 만들 때 사용)

sandbox/ 의 브랜치 (main 이 기본 브랜치):
  main                 기본 브랜치
  feature/login        main 에 병합됨 (병합 커밋)                      -> 삭제 대상
  fix/typo             main 에 병합됨 (fast-forward)                   -> 삭제 대상
  chore/deps           main 에 병합됨 (fast-forward)                   -> 삭제 대상
  wip/search           커밋이 main 에 없음 (병합 안 됨)                -> 보존
  feature/current      main 과 같은 지점. 병합된 상태지만 지금 체크아웃 중 -> 보존 (현재 브랜치)
이 예제의 .opencode/ 도 sandbox 로 복사되어 있다.
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
    dest.mkdir(parents=True)

    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=dest, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       stdin=subprocess.DEVNULL)

    def commit(filename: str, text: str, message: str) -> None:
        (dest / filename).write_text(text, encoding="utf-8", newline="\n")
        git("add", filename)
        git("commit", "-m", message)

    git("-c", "init.defaultBranch=main", "init")
    git("config", "user.name", "Demo User")
    git("config", "user.email", "demo.invalid")
    git("config", "commit.gpgsign", "false")
    git("config", "core.autocrlf", "false")
    # 첫 커밋에 스킬을 포함시켜 작업 트리를 깨끗하게 둔다
    shutil.copytree(HERE / ".opencode", dest / ".opencode",
                    ignore=shutil.ignore_patterns("node_modules", "package.json", "package-lock.json", "bun.lock", ".gitignore"))
    (dest / ".gitignore").write_text(".opencode/node_modules/\n.opencode/package.json\n.opencode/bun.lock\n",
                                     encoding="utf-8", newline="\n")
    git("add", ".")
    git("commit", "-m", "initial commit")
    commit("app.txt", "app v1\n", "add app")

    git("checkout", "-b", "feature/login")
    commit("login.txt", "login\n", "add login")
    git("checkout", "main")
    git("merge", "--no-ff", "-m", "merge feature/login", "feature/login")

    git("checkout", "-b", "fix/typo")
    commit("typo.txt", "typo fixed\n", "fix typo")
    git("checkout", "main")
    git("merge", "--ff-only", "fix/typo")

    git("checkout", "-b", "chore/deps")
    commit("deps.txt", "deps\n", "update deps")
    git("checkout", "main")
    git("merge", "--ff-only", "chore/deps")

    git("checkout", "-b", "wip/search")
    commit("search.txt", "search wip\n", "wip: search")
    git("checkout", "main")

    git("checkout", "-b", "feature/current")
    return dest


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    target = build(Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "sandbox")
    print(f"sandbox 준비 완료: {target}")
    print("다음 단계:")
    print("  cd sandbox")
    print("  git branch            (브랜치 6개)")
    print("  opencode")
    print("  > 병합된 브랜치 정리해줘")
