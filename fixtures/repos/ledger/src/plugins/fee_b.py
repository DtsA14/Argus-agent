"""Late fee caps for partner contracts (not applied automatically; finance applies them by hand)."""


def capped_fee_cents(fee_cents, amount_cents, cap_percent=10):
    """The late fee limited to a percentage of the amount."""
    return min(fee_cents, amount_cents * cap_percent // 100)
