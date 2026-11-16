"""Payment step. After charging it sends a receipt."""
from models import Order
from services import notifications


def charge(order: Order) -> None:
    order.paid = True
    notifications.send_receipt(order)
