"""Stock checks."""
import db


def has_stock(sku: str, qty: int) -> bool:
    return db.load_stock(sku) >= qty
