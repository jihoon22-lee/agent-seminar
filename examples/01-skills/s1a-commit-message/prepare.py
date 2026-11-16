"""s1a 실습용 git 저장소(sandbox/)를 만든다.

sandbox/ 안에는
  - 커밋 1개 (할인 가격 함수에 버그가 있는 상태),
  - 스테이징된 변경 (버그 수정 + 테스트 추가),
  - 브랜치 fix/42-negative-price
가 들어 있고, 이 예제의 .opencode/ 가 복사되어 있다.

여러 번 실행해도 매번 처음부터 다시 만든다.
    python prepare.py          (Linux 에서 python 이 없으면 python3 prepare.py)
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

PRICING_BEFORE = '''"""상품 가격 계산."""


def discount_price(price: int, percent: int) -> int:
    """정가(원)에서 percent % 를 깎은 금액을 돌려준다."""
    return price - price * percent // 100
'''

PRICING_AFTER = '''"""상품 가격 계산."""


def discount_price(price: int, percent: int) -> int:
    """정가(원)에서 percent % 를 깎은 금액을 돌려준다.

    percent 는 0~100 사이여야 한다.
    """
    if not 0 <= percent <= 100:
        raise ValueError(f"percent 는 0~100 이어야 합니다: {percent}")
    return price - price * percent // 100
'''

TEST_FILE = '''import unittest

from shop.pricing import discount_price


class DiscountPriceTest(unittest.TestCase):
    def test_normal(self):
        self.assertEqual(discount_price(10000, 10), 9000)

    def test_over_100_percent_is_rejected(self):
        with self.assertRaises(ValueError):
            discount_price(10000, 150)

    def test_negative_percent_is_rejected(self):
        with self.assertRaises(ValueError):
            discount_price(10000, -5)


if __name__ == "__main__":
    unittest.main()
'''


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
    (SANDBOX / "shop").mkdir(parents=True)
    (SANDBOX / "tests").mkdir()

    git("-c", "init.defaultBranch=main", "init")
    git("config", "user.name", "Demo User")
    git("config", "user.email", "demo@example.com")
    git("config", "commit.gpgsign", "false")
    git("config", "core.autocrlf", "false")

    # 이 예제의 스킬을 sandbox 로 복사 (첫 커밋에 포함시켜 스테이징된 변경과 섞이지 않게 한다)
    shutil.copytree(HERE / ".opencode", SANDBOX / ".opencode",
                    ignore=shutil.ignore_patterns("node_modules", "package.json", "package-lock.json",
                                                  "bun.lock", ".gitignore"))
    (SANDBOX / ".gitignore").write_text(".opencode/node_modules/\n__pycache__/\n", encoding="utf-8", newline="\n")
    (SANDBOX / "shop" / "__init__.py").write_text("", encoding="utf-8")
    (SANDBOX / "shop" / "pricing.py").write_text(PRICING_BEFORE, encoding="utf-8", newline="\n")
    git("add", ".")
    git("commit", "-m", "initial pricing module")
    git("checkout", "-b", "fix/42-negative-price")

    # 스테이징할 변경: 버그 수정 + 테스트
    (SANDBOX / "shop" / "pricing.py").write_text(PRICING_AFTER, encoding="utf-8", newline="\n")
    (SANDBOX / "tests" / "test_pricing.py").write_text(TEST_FILE, encoding="utf-8", newline="\n")
    git("add", "shop/pricing.py", "tests/test_pricing.py")

    print(f"sandbox 준비 완료: {SANDBOX}")
    print("다음 단계:")
    print("  cd sandbox")
    print("  opencode")
    print('  > 스테이징된 변경으로 커밋 메시지 작성해줘')


if __name__ == "__main__":
    main()
