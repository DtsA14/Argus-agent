"""Price estimates for quotes sent before an order is placed."""
from ..discounts.registry import active_rules
from ..discounts.rules import Rule
from ..pricing.base import Order, apply_rules

PROMO_PERCENT = 2


def quote_total(customer, items, promo=False):
    """Estimated total in cents; a quote promotion adds a small extra discount to this quote only."""
    order = Order(list(items))
    rules = active_rules(customer)
    if promo:
        rules.append(Rule("quote-promo", PROMO_PERCENT, lambda o: True))
    return apply_rules(order, rules)
