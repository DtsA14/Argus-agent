"""Refunds."""
from .money import parse_amount


def refund_total(amounts):
    """Total in cents of the refunded amounts (decimal texts)."""
    return sum(parse_amount(a) for a in amounts)
