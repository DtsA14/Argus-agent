"""Customer accounts."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Customer:
    id: str
    name: str
    blocked: bool = False
    segment: str = "standard"


def display_name(customer):
    """The name shown on receipts and in emails."""
    return customer.name.strip() or customer.id
