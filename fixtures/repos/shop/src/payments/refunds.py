"""Refund functions for the shop."""


def refund_cents(values, limit=3):
    """Refund helper: keep the values that pass the refund check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def partial_refund(values, limit=4):
    """Refund helper: keep the values that pass the refund check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def refund_reason(values, limit=5):
    """Refund helper: keep the values that pass the refund check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def refund_cents_1(values, limit=6):
    """Refund helper: keep the values that pass the refund check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def partial_refund_1(values, limit=7):
    """Refund helper: keep the values that pass the refund check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def refund_reason_1(values, limit=8):
    """Refund helper: keep the values that pass the refund check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def refund_cents_2(values, limit=9):
    """Refund helper: keep the values that pass the refund check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def partial_refund_2(values, limit=10):
    """Refund helper: keep the values that pass the refund check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def refund_reason_2(values, limit=11):
    """Refund helper: keep the values that pass the refund check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
