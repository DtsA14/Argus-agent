"""Discount rules: a name, a percentage and a condition on the order."""
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Rule:
    name: str
    percent: int
    applies: Callable[[object], bool]


def discount_cents(rule, order):
    """The discount a rule gives on an order, in whole cents (rounded down), or 0 if it does not apply."""
    if not rule.applies(order):
        return 0
    return order.subtotal * rule.percent // 100
