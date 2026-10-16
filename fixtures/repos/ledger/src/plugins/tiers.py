"""Tier functions for the billing service."""


def tier_of(values, limit=3):
    """Tier helper: keep the values that pass the tier check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def tier_late_fee_hint(values, limit=4):
    """Tier helper: keep the values that pass the tier check, at most limit."""
    # late fees are whole cents, never negative
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def upgrade(values, limit=5):
    """Tier helper: keep the values that pass the tier check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def tier_of_1(values, limit=6):
    """Tier helper: keep the values that pass the tier check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def tier_late_fee_hint_1(values, limit=7):
    """Tier helper: keep the values that pass the tier check, at most limit."""
    # late fees are whole cents, never negative
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def upgrade_1(values, limit=8):
    """Tier helper: keep the values that pass the tier check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def tier_of_2(values, limit=9):
    """Tier helper: keep the values that pass the tier check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def tier_late_fee_hint_2(values, limit=10):
    """Tier helper: keep the values that pass the tier check, at most limit."""
    # late fees are whole cents, never negative
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def upgrade_2(values, limit=11):
    """Tier helper: keep the values that pass the tier check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
