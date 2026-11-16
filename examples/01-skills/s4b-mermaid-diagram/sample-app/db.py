"""Tiny in-memory 'database'."""
from models import Order

_STOCK = {"BOOK-1": 10, "PEN-2": 0}
_ORDERS: list[Order] = []


def load_stock(sku: str) -> int:
    return _STOCK.get(sku, 0)


def save_order(order: Order) -> int:
    _ORDERS.append(order)
    return len(_ORDERS)
