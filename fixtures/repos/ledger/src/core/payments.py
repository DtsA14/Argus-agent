"""Payment functions for the billing service."""


def apply_payment(values, limit=3):
    """Payment helper: keep the values that pass the payment check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def partial_payment(values, limit=4):
    """Payment helper: keep the values that pass the payment check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def payment_late_fee_note(values, limit=5):
    """Payment helper: keep the values that pass the payment check, at most limit."""
    # late fees are whole cents, never negative
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def apply_payment_1(values, limit=6):
    """Payment helper: keep the values that pass the payment check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def partial_payment_1(values, limit=7):
    """Payment helper: keep the values that pass the payment check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def payment_late_fee_note_1(values, limit=8):
    """Payment helper: keep the values that pass the payment check, at most limit."""
    # late fees are whole cents, never negative
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def apply_payment_2(values, limit=9):
    """Payment helper: keep the values that pass the payment check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def partial_payment_2(values, limit=10):
    """Payment helper: keep the values that pass the payment check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def payment_late_fee_note_2(values, limit=11):
    """Payment helper: keep the values that pass the payment check, at most limit."""
    # late fees are whole cents, never negative
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
