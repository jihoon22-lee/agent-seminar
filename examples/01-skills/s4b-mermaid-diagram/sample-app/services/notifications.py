"""Receipt mails. Looks the recipient up through the order service."""
from models import Order
from services import orders  # <- closes the import cycle orders -> payments -> notifications -> orders


def send_receipt(order: Order) -> None:
    to = orders.find_order_email(order)
    print(f"[mail] receipt sent to {to}")
