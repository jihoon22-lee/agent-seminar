"""s2c 실습용 프로젝트(sandbox/)를 만든다.

sandbox/ 는 git 저장소이고, 이미 ADR 한 개(docs/adr/0001-...)가 들어 있다.
그래서 스킬이 "다음 번호"를 0002 로 정하는지 확인할 수 있다.
이 예제의 .opencode/ 가 복사되어 있다.

    python prepare.py          (Linux 에서 python 이 없으면 python3 prepare.py)
    cd sandbox && opencode
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
EXAMPLE_ADR = HERE / ".opencode" / "skills" / "adr" / "examples" / "0001-use-postgresql-for-order-store.md"


def _force_remove(func, path, _exc):
    # Windows 는 .git 안의 읽기 전용 파일을 그냥 지우지 못한다.
    os.chmod(path, stat.S_IWRITE)
    func(path)


def git(*args: str) -> None:
    subprocess.run(["git", *args], cwd=SANDBOX, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main() -> None:
    if SANDBOX.exists():
        shutil.rmtree(SANDBOX, onerror=_force_remove)
    (SANDBOX / "docs" / "adr").mkdir(parents=True)

    git("-c", "init.defaultBranch=main", "init")
    git("config", "user.name", "Demo User")
    git("config", "user.email", "demo@example.com")
    git("config", "commit.gpgsign", "false")
    git("config", "core.autocrlf", "false")

    shutil.copytree(HERE / ".opencode", SANDBOX / ".opencode",
                    ignore=shutil.ignore_patterns("node_modules", "package.json", "package-lock.json",
                                                  "bun.lock", ".gitignore"))
    shutil.copyfile(EXAMPLE_ADR, SANDBOX / "docs" / "adr" / EXAMPLE_ADR.name)
    (SANDBOX / "README.md").write_text("# 주문 서비스\n\nADR 은 docs/adr/ 에 둔다.\n", encoding="utf-8", newline="\n")
    (SANDBOX / ".gitignore").write_text(".opencode/node_modules/\n", encoding="utf-8", newline="\n")
    git("add", ".")
    git("commit", "-m", "docs: 첫 ADR 추가")

    print(f"sandbox 준비 완료: {SANDBOX}")
    print("다음 단계:")
    print("  cd sandbox")
    print("  opencode")
    print("  > 메시지 큐로 Kafka 대신 RabbitMQ를 쓰기로 한 결정을 ADR로 남겨줘")


if __name__ == "__main__":
    main()
