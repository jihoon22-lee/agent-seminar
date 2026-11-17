#!/usr/bin/env python3
"""prepare.py - M13 준비: 연습용 git 저장소(sandbox/)를 처음부터 만든다.

작은 이력(커밋 7개, 작성자 dev-alpha / dev-beta 두 명)이 들어 있다. 실행할 때마다 sandbox/를 지우고
다시 만들며, 커밋 날짜·작성자를 고정해서 항상 같은 해시가 나온다.
server.py와 opencode.json은 이력에 넣지 않고 sandbox/ 안에 복사만 한다. (opencode를 sandbox/에서 실행하기 위해)

    python prepare.py
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
SANDBOX = HERE / "sandbox"

# --- pricing.py 를 블록 단위로 쌓는다 (blame 하면 줄마다 작성자가 갈리도록) ----------------
HEAD_BLOCK = '''"""주문 금액 계산 모듈 (연습용)."""

TAX_RATE = 0.1


def subtotal(items):
    """상품 목록 [(이름, 단가, 수량), ...]의 합계."""
    total = 0
    for _name, price, qty in items:
        total += price * qty
    return total


def tax(amount):
    """세금을 계산한다."""
    return int(amount * TAX_RATE)
'''

DISCOUNT_BLOCK = '''

def volume_discount(qty):
    """수량 할인율. 10개 이상 5%, 50개 이상 10%."""
    if qty >= 50:
        return 0.10
    if qty >= 10:
        return 0.05
    return 0.0


def apply_discount(amount, rate):
    """금액에서 할인율만큼 뺀다."""
    if not 0 <= rate < 1:
        raise ValueError("할인율은 0 이상 1 미만이어야 한다")
    return amount - int(amount * rate)


def order_total(items):
    """할인과 세금을 반영한 최종 금액."""
    qty = sum(q for _n, _p, q in items)
    base = apply_discount(subtotal(items), volume_discount(qty))
    return base + tax(base)
'''

COUPON_BLOCK = '''

MAX_COUPON = 10000


def apply_coupon(amount, coupon):
    """정액 쿠폰을 적용한다. 쿠폰은 최대 1만 원, 금액 아래로는 내려가지 않는다."""
    coupon = min(coupon, MAX_COUPON)
    return max(amount - coupon, 0)


def checkout(items, coupon=0):
    """쿠폰까지 반영한 결제 금액."""
    return apply_coupon(order_total(items), coupon)
'''

DESIGN_DOC = """# 가격 계산 설계 메모

- 금액은 원 단위 정수로만 다룬다.
- 할인은 세금 계산 전에 적용한다.
- 쿠폰은 세금까지 계산한 최종 금액에서 뺀다. 쿠폰 상한은 1만 원이다.
"""

# (작성자, 날짜, 메시지, 적용 함수) - 적용 함수는 sandbox 경로를 받아 파일을 바꾼다
AUTHORS = {"alpha": "dev-alpha", "beta": "dev-beta"}


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def read(root: Path, rel: str) -> str:
    return (root / rel).read_text(encoding="utf-8")


def c1(r):
    write(r, "src/pricing.py", HEAD_BLOCK)
    write(r, "README.md", "# 가격 계산 연습 저장소\n")


def c2(r):
    write(r, "src/pricing.py", read(r, "src/pricing.py") + DISCOUNT_BLOCK)


def c3(r):
    write(r, "src/pricing.py", read(r, "src/pricing.py").replace(
        "    return int(amount * TAX_RATE)", "    return round(amount * TAX_RATE)  # 버림이 아니라 반올림"))


def c4(r):
    write(r, "docs/설계.md", DESIGN_DOC)


def c5(r):
    write(r, "src/pricing.py", read(r, "src/pricing.py") + COUPON_BLOCK)


def c6(r):
    write(r, "src/pricing.py", read(r, "src/pricing.py").replace(
        '"""수량 할인율. 10개 이상 5%, 50개 이상 10%."""', '"""수량 할인율: 10개 이상 5%, 50개 이상 10%."""'))


def c7(r):
    write(r, "README.md", read(r, "README.md") + "\n설계 메모는 docs/설계.md 를 본다.\n")


COMMITS = [
    ("alpha", "2026-03-02T10:00:00+09:00", "가격 계산 모듈 초기 버전", c1),
    ("beta", "2026-03-04T14:30:00+09:00", "수량 할인과 최종 금액 계산 추가", c2),
    ("alpha", "2026-03-06T09:15:00+09:00", "세금 계산을 반올림으로 수정", c3),
    ("beta", "2026-03-09T16:40:00+09:00", "설계 메모 추가", c4),
    ("alpha", "2026-03-12T11:05:00+09:00", "정액 쿠폰과 상한 추가", c5),
    ("beta", "2026-03-13T17:20:00+09:00", "할인 함수 설명 문구 정리", c6),
    ("alpha", "2026-03-16T10:10:00+09:00", "README에 설계 메모 안내 추가", c7),
]


def git(root: Path, *args: str, env_extra: dict | None = None) -> None:
    env = dict(os.environ)
    env.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"})
    env.update(env_extra or {})
    subprocess.run(["git", "-c", "core.quotepath=false", "-c", "core.autocrlf=false", *args], cwd=str(root), env=env,
                   check=True, capture_output=True)


def _force_rm(func, path, _exc):  # noqa: ANN001
    import stat
    os.chmod(path, stat.S_IWRITE)  # Windows: .git 안의 읽기 전용 파일
    func(path)


def build() -> Path:
    if SANDBOX.exists():
        if sys.version_info >= (3, 12):
            shutil.rmtree(SANDBOX, onexc=_force_rm)
        else:
            shutil.rmtree(SANDBOX, onerror=_force_rm)
    SANDBOX.mkdir()
    git(SANDBOX, "init", "-q", "-b", "main")
    for who, date, message, apply in COMMITS:
        apply(SANDBOX)
        git(SANDBOX, "add", "-A")
        name = AUTHORS[who]
        # 이메일은 비워 둔다. 개인 정보가 들어갈 자리가 없다.
        env = {"GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": "", "GIT_AUTHOR_DATE": date,
               "GIT_COMMITTER_NAME": name, "GIT_COMMITTER_EMAIL": "", "GIT_COMMITTER_DATE": date}
        git(SANDBOX, "commit", "-q", "-m", message, env_extra=env)
    # opencode를 sandbox/에서 실행할 수 있게 서버와 설정을 복사한다 (git 이력에는 넣지 않는다)
    shutil.copy2(HERE / "server.py", SANDBOX / "server.py")
    shutil.copy2(HERE / "opencode.json", SANDBOX / "opencode.json")
    return SANDBOX


if __name__ == "__main__":
    build()
    log = subprocess.run(["git", "-c", "core.quotepath=false", "log", "--format=%h %an %ad %s", "--date=short"],
                         cwd=str(SANDBOX), capture_output=True, encoding="utf-8").stdout
    print(f"sandbox 저장소를 만들었다: {SANDBOX}\n")
    print(log)
    print("다음: cd sandbox  그리고  opencode mcp list")
