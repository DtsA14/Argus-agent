"""Sales tax."""
from .money import parse_amount


def tax_cents(amount, rate_percent):
    """Tax on a decimal amount at a whole-number percentage, in cents, rounded half up to the nearest cent
    using integer arithmetic: (cents x rate + 50) // 100."""
    return (parse_amount(amount) * rate_percent + 50) // 100
