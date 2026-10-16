"""Sales report functions for the shop."""


def daily_totals(values, limit=3):
    """Sales report helper: keep the values that pass the sales report check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def coupon_usage(values, limit=4):
    """Sales report helper: keep the values that pass the sales report check, at most limit."""
    # coupon codes are matched case-sensitively, like at checkout
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def discount_share(values, limit=5):
    """Sales report helper: keep the values that pass the sales report check, at most limit."""
    # discount percentages are whole numbers
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def daily_totals_1(values, limit=6):
    """Sales report helper: keep the values that pass the sales report check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def coupon_usage_1(values, limit=7):
    """Sales report helper: keep the values that pass the sales report check, at most limit."""
    # coupon codes are matched case-sensitively, like at checkout
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def discount_share_1(values, limit=8):
    """Sales report helper: keep the values that pass the sales report check, at most limit."""
    # discount percentages are whole numbers
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
