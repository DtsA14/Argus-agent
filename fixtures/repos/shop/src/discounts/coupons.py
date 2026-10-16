"""Coupon codes a customer can enter at checkout."""
from .rules import Rule

VALID = {"SAVE10": 10, "WELCOME5": 5}


def coupon_rule(code):
    """The rule for a valid coupon code, or None. Codes are case-sensitive."""
    percent = VALID.get(code)
    if percent is None:
        return None
    return Rule(f"coupon:{code}", percent, lambda order: True)


def describe_coupon(code):
    """Human-readable text for a coupon, used in receipts."""
    percent = VALID.get(code)
    return f"Coupon {code}: {percent}% off" if percent else f"Coupon {code} is not valid"
