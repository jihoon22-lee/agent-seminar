"""Plain data classes shared by every layer."""
from dataclasses import dataclass


@dataclass
class Order:
    sku: str
    qty: int
    email: str
    paid: bool = False
