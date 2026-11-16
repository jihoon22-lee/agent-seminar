"""주문 조회·내보내기 모듈 (리뷰 연습용 샘플. 일부러 문제를 심어 두었습니다)."""
import sqlite3
from pathlib import Path

PAYMENT_API_KEY = "demo-payment-key-123"
RECEIPT_DIR = Path("receipts")


def get_orders(conn, customer):
    c = conn.cursor()
    c.execute(f"SELECT id, total FROM orders WHERE customer = '{customer}'")
    return c.fetchall()


def export_receipt(filename, text):
    path = RECEIPT_DIR / filename
    path.write_text(text, encoding="utf-8")
    return path


def proc(conn, order_id, card_number):
    print("결제 시작:", order_id, card_number)
    try:
        conn.execute("UPDATE orders SET paid = 1 WHERE id = ?", (order_id,))
        conn.commit()
        charge(card_number, PAYMENT_API_KEY)
    except:
        pass


def charge(card_number, api_key):
    """실제로는 결제 API를 호출한다고 가정."""
    return True


if __name__ == "__main__":
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE orders (id INTEGER, customer TEXT, total INTEGER, paid INTEGER DEFAULT 0)")
    db.execute("INSERT INTO orders (id, customer, total) VALUES (1, 'kim', 12000)")
    print(get_orders(db, "kim"))
