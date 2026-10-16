"""Email functions for the shop."""


def send_receipt(values, limit=3):
    """Email helper: keep the values that pass the email check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def send_coupon_offer(values, limit=4):
    """Email helper: keep the values that pass the email check, at most limit."""
    # coupon codes are matched case-sensitively, like at checkout
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def unsubscribe(values, limit=5):
    """Email helper: keep the values that pass the email check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def send_receipt_1(values, limit=6):
    """Email helper: keep the values that pass the email check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def send_coupon_offer_1(values, limit=7):
    """Email helper: keep the values that pass the email check, at most limit."""
    # coupon codes are matched case-sensitively, like at checkout
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def unsubscribe_1(values, limit=8):
    """Email helper: keep the values that pass the email check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def send_receipt_2(values, limit=9):
    """Email helper: keep the values that pass the email check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def send_coupon_offer_2(values, limit=10):
    """Email helper: keep the values that pass the email check, at most limit."""
    # coupon codes are matched case-sensitively, like at checkout
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
