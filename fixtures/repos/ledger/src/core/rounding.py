"""Rounding of amounts in cents."""


def percent_of(amount_cents, percent):
    """A whole percentage of an amount, rounded down to the cent."""
    return amount_cents * percent // 100


def split_cents(total_cents, parts):
    """Split an amount into nearly equal parts that add up exactly."""
    base, rest = divmod(total_cents, parts)
    return [base + (1 if i < rest else 0) for i in range(parts)]
