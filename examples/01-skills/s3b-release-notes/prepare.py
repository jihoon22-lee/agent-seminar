#!/usr/bin/env python3
"""sandbox/ 에 샘플 git 저장소를 만든다 (v1.0.0 태그 + 그 뒤 커밋 12개).

sandbox/ 는 자체 `git init` 이고, 이 예제의 .opencode/ 가 복사되어 들어간다.
다시 실행하면 sandbox/ 를 지우고 처음부터 다시 만든다.

사용: python prepare.py   (Linux에서 python이 없으면 python3 prepare.py)
"""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SANDBOX = HERE / "sandbox"

ENV = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
ENV.pop("GIT_DIR", None)

# (day, author, message, file, line appended to file)
BASE = [("2026-10-01", "dev-alpha", "chore: initial commit", "README.md", "# shop-demo")]
BEFORE_TAG = [
    ("2026-10-05", "dev-alpha", "feat: add product list endpoint", "api.py", "def list_products(): ..."),
    ("2026-10-08", "dev-alpha", "fix: handle empty cart on checkout", "cart.py", "def checkout(cart): ..."),
]
AFTER_TAG = [
    ("2026-10-12", "dev-beta", "feat(cart): add coupon code support", "cart.py", "def apply_coupon(cart, code): ..."),
    ("2026-10-13", "dev-beta", "fix(cart): round totals to whole won", "cart.py", "def total(cart): ..."),
    ("2026-10-14", "dev-gamma", "perf(api): cache product list for 60 seconds", "api.py", "CACHE_TTL = 60"),
    ("2026-10-15", "dev-gamma", "fix: prevent duplicate orders on double click", "api.py", "def create_order(): ..."),
    ("2026-10-15", "dev-gamma", "fix(auth): refresh expired session token instead of logging out", "auth.py", "def refresh(): ..."),
    ("2026-10-16", "dev-alpha", "docs: describe the coupon API in README", "README.md", "coupon docs"),
    ("2026-10-19", "dev-beta", "refactor(db): extract connection helper", "db.py", "def connect(): ..."),
    ("2026-10-20", "dev-gamma", "feat(search)!: replace /search?q= with /v2/search\n\nBREAKING CHANGE: the old /search endpoint is removed; clients must call /v2/search.",
     "api.py", "def search_v2(): ..."),
    ("2026-10-21", "dev-alpha", "test: cover coupon edge cases", "test_cart.py", "def test_coupon(): ..."),
    ("2026-10-22", "dev-beta", "ci: run tests on every pull request", "ci.yml", "on: pull_request"),
    ("2026-10-23", "dev-gamma", "update stuff", "misc.txt", "tweak"),  # not a Conventional Commit on purpose
    ("2026-10-26", "dev-alpha", "feat(auth): support login with one-time email code", "auth.py", "def email_code_login(): ..."),
]


def git(*args: str, date: str | None = None, author: str = "dev-alpha") -> None:
    env = dict(ENV, GIT_AUTHOR_NAME=author, GIT_COMMITTER_NAME=author,
               GIT_AUTHOR_EMAIL="demo@example.invalid", GIT_COMMITTER_EMAIL="demo@example.invalid")
    if date:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = f"{date}T12:00:00+09:00"
    subprocess.run(["git", "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false", *args],
                   cwd=SANDBOX, env=env, check=True, capture_output=True, encoding="utf-8")


def commit(entry: tuple[str, str, str, str, str]) -> None:
    day, author, message, filename, line = entry
    with open(SANDBOX / filename, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(line + "\n")
    git("add", filename)
    git("commit", "-m", message, date=day, author=author)


def rmtree(path: Path) -> None:
    def onerror(func, p, _exc):  # Windows: .git objects are read-only
        os.chmod(p, stat.S_IWRITE)
        func(p)
    shutil.rmtree(path, onerror=onerror)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    if SANDBOX.exists():
        rmtree(SANDBOX)
    SANDBOX.mkdir()
    git("init", "-q", "-b", "main")
    for entry in BASE + BEFORE_TAG:
        commit(entry)
    git("tag", "-a", "v1.0.0", "-m", "v1.0.0", date="2026-10-09")
    for entry in AFTER_TAG:
        commit(entry)
    shutil.copytree(HERE / ".opencode", SANDBOX / ".opencode", ignore=shutil.ignore_patterns("node_modules", "package*.json", "bun.lock"))
    if (HERE / "opencode.json").exists():
        shutil.copy2(HERE / "opencode.json", SANDBOX / "opencode.json")
    print(f"sandbox 준비 완료: {SANDBOX}")
    print(f"커밋 {len(AFTER_TAG)}개가 v1.0.0 태그 뒤에 있습니다.")
    print("다음 단계:")
    print("  cd sandbox")
    print("  opencode")
    print("  > v1.0.0 이후 변경사항으로 릴리스 노트를 써줘")


if __name__ == "__main__":
    main()
