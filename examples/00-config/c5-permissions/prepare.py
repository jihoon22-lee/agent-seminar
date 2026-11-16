"""C5 준비: 권한 실험용 sandbox/ 를 만든다 (git 저장소 + 지워도 되는 파일). 다시 실행해도 안전하다.

    python prepare.py

만드는 것
  sandbox/                  자체 git 저장소. 이 예제의 opencode.json 이 복사되어 있다.
  sandbox/notes.txt         edit 권한 실험용 (커밋된 상태)
  sandbox/victim.txt        `rm *` deny 실험용 (커밋된 상태)
  <임시폴더>/c5-outside/note.txt   프로젝트 밖 파일: external_directory 실험용
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
SANDBOX = HERE / "sandbox"
OUTSIDE = Path(tempfile.gettempdir()) / "c5-outside"


def git(*args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=c5", "-c", "user.email=c5@example.invalid", *args],
        cwd=str(SANDBOX), check=True, capture_output=True, stdin=subprocess.DEVNULL,
    )


def main() -> None:
    shutil.rmtree(SANDBOX, ignore_errors=True)
    SANDBOX.mkdir()
    shutil.copyfile(HERE / "opencode.json", SANDBOX / "opencode.json")
    (SANDBOX / "notes.txt").write_text("첫 줄: 권한 실험용 메모\n", encoding="utf-8")
    (SANDBOX / "victim.txt").write_text("이 파일은 삭제 실험용입니다.\n", encoding="utf-8")
    git("init", "-q")
    git("add", "-A")
    git("commit", "-q", "-m", "c5 sandbox")
    OUTSIDE.mkdir(exist_ok=True)
    (OUTSIDE / "note.txt").write_text("프로젝트 밖에 있는 파일입니다.\n", encoding="utf-8")

    print(f"만들었습니다: {SANDBOX}")
    print(f"프로젝트 밖 파일: {OUTSIDE / 'note.txt'}")
    print()
    print("  PowerShell:  cd sandbox; opencode")
    print("  Linux bash:  cd sandbox && opencode")
    print("(평소 쓰는 모델로 실행하면 됩니다. 모델 설정이 없다면 opencode -m opencode/big-pickle)")


if __name__ == "__main__":
    main()
