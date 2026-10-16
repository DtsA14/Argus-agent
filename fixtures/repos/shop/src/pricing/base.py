"""Order totals."""
from dataclasses import dataclass, field

from ..discounts.rules import discount_cents


@dataclass
class Order:
    items: list = field(default_factory=list)   # (sku, unit_price_cents, quantity)

    @property
    def subtotal(self):
        return sum(price * qty for _, price, qty in self.items)


def apply_rules(order, rules):
    """The order total in cents after every applicable rule's discount (each computed on the subtotal)."""
    return order.subtotal - sum(discount_cents(rule, order) for rule in rules)
