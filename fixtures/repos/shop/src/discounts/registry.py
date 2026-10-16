"""Discount rules that apply to every customer.

active_rules() gives each caller its own list of the rules that currently apply; callers may extend it with
order-specific rules (a coupon, a quote promotion) without affecting anyone else.
"""
from .rules import Rule

RULES = [
    Rule("volume", 5, lambda order: order.subtotal >= 10000),
]


def active_rules(customer):
    """The discount rules that apply to this customer's orders."""
    if customer.blocked:
        return []
    return RULES
