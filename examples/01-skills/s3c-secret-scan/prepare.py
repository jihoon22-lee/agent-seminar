#!/usr/bin/env python3
"""sandbox/ 에 '비밀값이 실수로 섞인' 샘플 git 저장소를 만든다.

가짜 비밀값은 실행할 때 문자열을 이어 붙여서 만든다. 저장소에 커밋된 파일에는 토큰 모양의
문자열이 하나도 없다(GitHub push protection 이 막기 때문). 값은 모두 무작위 가짜이고 어디에도 쓸 수 없다.

sandbox/ 의 상태:
  - 커밋됨: README.md, app.py(환경 변수를 올바르게 사용), .env.example
  - 커밋 안 됨(스테이징 또는 untracked): config.py, .env, deploy/id_demo, notes.md
다시 실행하면 sandbox/ 를 지우고 처음부터 만든다.

사용: python prepare.py   (Linux에서 python이 없으면 python3 prepare.py)
"""
from __future__ import annotations

import os
import random
import shutil
import stat
import string
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SANDBOX = HERE / "sandbox"
ENV = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
           GIT_AUTHOR_NAME="demo", GIT_COMMITTER_NAME="demo",
           GIT_AUTHOR_EMAIL="demo@example.invalid", GIT_COMMITTER_EMAIL="demo@example.invalid")
ENV.pop("GIT_DIR", None)


def make_secrets() -> dict[str, str]:
    """Deterministic fake secrets, assembled at runtime from short pieces."""
    rng = random.Random(4242)
    alnum = string.ascii_letters + string.digits

    def rand(n: int, alphabet: str = alnum) -> str:
        return "".join(rng.choice(alphabet) for _ in range(n))

    return {
        "api_key": "sk" + "-" + rand(40),                       # looks like an LLM-vendor key
        "github": "gh" + "p_" + rand(36),                        # looks like a GitHub token
        "aws_id": "AK" + "IA" + rand(16, string.ascii_uppercase + string.digits),
        "db_password": rand(14),
        "session_secret": rand(32, string.hexdigits.lower()),    # 32 hex chars
        "stripe_like": "sk" + "_live_" + rand(24),
        "build_sha": rand(40, "0123456789abcdef"),               # a git SHA: legit-looking false positive
    }


def files(s: dict[str, str]) -> tuple[dict[str, str], dict[str, str]]:
    committed = {
        "README.md": "# shop-demo\n\n설정은 환경 변수로 읽는다. 예: `export API_KEY=<your key>`\n",
        "app.py": ('import os\n\n'
                   'API_KEY = os.environ["API_KEY"]\n'
                   'DB_PASSWORD = os.environ.get("DB_PASSWORD", "")\n\n'
                   'def main():\n    print("shop-demo started")\n'),
        ".env.example": "API_KEY=\nDB_PASSWORD=\nSESSION_SECRET=\n",
    }
    work = {
        "config.py": ('"""Quick local config -- TODO remove before commit."""\n'
                      f'API_KEY = "{s["api_key"]}"\n'
                      f'DB_PASSWORD = "{s["db_password"]}"\n'
                      'SMTP_PASSWORD = "changeme"\n'
                      'DEBUG = True\n'
                      f'BUILD_ID = "{s["build_sha"]}"\n'),
        ".env": (f'API_KEY={s["api_key"]}\n'
                 f'DATABASE_URL=postgres://app:{s["db_password"]}@localhost:5432/shop\n'
                 f'SESSION_SECRET={s["session_secret"]}\n'
                 'LOG_LEVEL=debug\n'),
        "deploy/ci.yml": ('steps:\n'
                          f'  - run: git clone https://ci-bot:{s["github"]}@example.invalid/shop.git\n'
                          f'    env: {{ AWS_ACCESS_KEY_ID: {s["aws_id"]} }}\n'),
        "deploy/id_demo": ("-----" + "BEGIN " + "OPENSSH " + "PRIVATE " + "KEY" + "-----\n"
                           "(demo: key body omitted)\n"
                           "-----" + "END " + "OPENSSH " + "PRIVATE " + "KEY" + "-----\n"),
        "notes.md": ("# 메모\n\n- 결제 연동 키: 대시보드에서 발급\n"
                     f'- 임시: stripe = "{s["stripe_like"]}"  # 테스트 후 폐기\n'
                     '- 이 줄은 일부러 무시: password = "hunter2hunter2"  # secret-scan: ignore\n'),
    }
    return committed, work


def git(*args: str) -> None:
    subprocess.run(["git", "-c", "commit.gpgsign=false", *args], cwd=SANDBOX, env=ENV, check=True,
                   capture_output=True, encoding="utf-8")


def write(rel: str, content: str) -> None:
    path = SANDBOX / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def rmtree(path: Path) -> None:
    def onerror(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    shutil.rmtree(path, onerror=onerror)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    if SANDBOX.exists():
        rmtree(SANDBOX)
    SANDBOX.mkdir()
    git("init", "-q", "-b", "main")
    committed, work = files(make_secrets())
    for rel, content in committed.items():
        write(rel, content)
    git("add", ".")
    git("commit", "-q", "-m", "chore: initial commit")
    for rel, content in work.items():
        write(rel, content)
    git("add", "config.py")  # staged; the rest stays untracked
    shutil.copytree(HERE / ".opencode", SANDBOX / ".opencode",
                    ignore=shutil.ignore_patterns("node_modules", "package*.json", "bun.lock"))
    print(f"sandbox 준비 완료: {SANDBOX}")
    print("  커밋됨: README.md app.py .env.example / 스테이징: config.py / untracked: .env deploy/ notes.md")
    print("다음 단계:")
    print("  cd sandbox")
    print("  opencode")
    print("  > 커밋하기 전에 비밀값이 섞였는지 검사해줘")


if __name__ == "__main__":
    main()
