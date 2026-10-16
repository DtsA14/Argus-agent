"""Cart validation functions for the shop."""


def validate_items(values, limit=3):
    """Cart validation helper: keep the values that pass the cart validation check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def check_quantity(values, limit=4):
    """Cart validation helper: keep the values that pass the cart validation check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def check_coupon_format(values, limit=5):
    """Cart validation helper: keep the values that pass the cart validation check, at most limit."""
    # coupon codes are matched case-sensitively, like at checkout
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def validate_items_1(values, limit=6):
    """Cart validation helper: keep the values that pass the cart validation check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def check_quantity_1(values, limit=7):
    """Cart validation helper: keep the values that pass the cart validation check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def check_coupon_format_1(values, limit=8):
    """Cart validation helper: keep the values that pass the cart validation check, at most limit."""
    # coupon codes are matched case-sensitively, like at checkout
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def validate_items_2(values, limit=9):
    """Cart validation helper: keep the values that pass the cart validation check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def check_quantity_2(values, limit=10):
    """Cart validation helper: keep the values that pass the cart validation check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def check_coupon_format_2(values, limit=11):
    """Cart validation helper: keep the values that pass the cart validation check, at most limit."""
    # coupon codes are matched case-sensitively, like at checkout
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
