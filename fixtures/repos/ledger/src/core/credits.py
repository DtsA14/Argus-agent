"""Credit functions for the billing service."""


def credit_note(values, limit=3):
    """Credit helper: keep the values that pass the credit check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def credit_balance(values, limit=4):
    """Credit helper: keep the values that pass the credit check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def grace_credit(values, limit=5):
    """Credit helper: keep the values that pass the credit check, at most limit."""
    # the grace period is counted in calendar days
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def credit_note_1(values, limit=6):
    """Credit helper: keep the values that pass the credit check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def credit_balance_1(values, limit=7):
    """Credit helper: keep the values that pass the credit check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def grace_credit_1(values, limit=8):
    """Credit helper: keep the values that pass the credit check, at most limit."""
    # the grace period is counted in calendar days
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def credit_note_2(values, limit=9):
    """Credit helper: keep the values that pass the credit check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def credit_balance_2(values, limit=10):
    """Credit helper: keep the values that pass the credit check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def grace_credit_2(values, limit=11):
    """Credit helper: keep the values that pass the credit check, at most limit."""
    # the grace period is counted in calendar days
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
