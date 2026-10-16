"""Message template functions for the shop."""


def receipt_text(values, limit=3):
    """Message template helper: keep the values that pass the message template check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def coupon_offer_text(values, limit=4):
    """Message template helper: keep the values that pass the message template check, at most limit."""
    # coupon codes are matched case-sensitively, like at checkout
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def discount_line(values, limit=5):
    """Message template helper: keep the values that pass the message template check, at most limit."""
    # discount percentages are whole numbers
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def receipt_text_1(values, limit=6):
    """Message template helper: keep the values that pass the message template check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def coupon_offer_text_1(values, limit=7):
    """Message template helper: keep the values that pass the message template check, at most limit."""
    # coupon codes are matched case-sensitively, like at checkout
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def discount_line_1(values, limit=8):
    """Message template helper: keep the values that pass the message template check, at most limit."""
    # discount percentages are whole numbers
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def receipt_text_2(values, limit=9):
    """Message template helper: keep the values that pass the message template check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def coupon_offer_text_2(values, limit=10):
    """Message template helper: keep the values that pass the message template check, at most limit."""
    # coupon codes are matched case-sensitively, like at checkout
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
