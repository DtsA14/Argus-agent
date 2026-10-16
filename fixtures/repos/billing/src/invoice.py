"""Invoice totals."""
from .money import parse_amount


def invoice_total(lines):
    """Total in cents of (description, unit_price_text, quantity) lines: the sum of price x quantity."""
    return sum(parse_amount(price) * quantity for _, price, quantity in lines)
