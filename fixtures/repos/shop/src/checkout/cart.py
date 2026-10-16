"""Checkout: the total a customer pays for a cart."""
from ..discounts.coupons import coupon_rule
from ..discounts.registry import active_rules
from ..pricing.base import Order, apply_rules


def checkout_total(customer, items, coupon=None):
    """Total in cents for the items, with the customer's discount rules and an optional coupon code."""
    order = Order(list(items))
    rules = active_rules(customer)
    rule = coupon_rule(coupon) if coupon else None
    if rule is not None:
        rules.append(rule)
    return apply_rules(order, rules)
