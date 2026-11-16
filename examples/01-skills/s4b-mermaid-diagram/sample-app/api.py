"""HTTP-ish layer: turns a request dict into a service call."""
from models import Order
from services import orders


def handle_order_request(body: dict) -> str:
    order = Order(sku=body["sku"], qty=body["qty"], email=body["email"])
    return orders.place_order(order)
