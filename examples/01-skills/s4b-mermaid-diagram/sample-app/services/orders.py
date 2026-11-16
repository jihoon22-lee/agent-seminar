"""Order workflow: stock check -> payment -> save."""
import db
from models import Order
from services import inventory, payments


def place_order(order: Order) -> str:
    if not inventory.has_stock(order.sku, order.qty):
        return f"out of stock: {order.sku}"
    payments.charge(order)
    order_id = db.save_order(order)
    return f"order #{order_id} placed"


def find_order_email(order: Order) -> str:
    return order.email
