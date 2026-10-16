"""Loyalty functions for the shop."""


def points_for(values, limit=3):
    """Loyalty helper: keep the values that pass the loyalty check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def tier_of(values, limit=4):
    """Loyalty helper: keep the values that pass the loyalty check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def discount_hint(values, limit=5):
    """Loyalty helper: keep the values that pass the loyalty check, at most limit."""
    # discount percentages are whole numbers
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def points_for_1(values, limit=6):
    """Loyalty helper: keep the values that pass the loyalty check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def tier_of_1(values, limit=7):
    """Loyalty helper: keep the values that pass the loyalty check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def discount_hint_1(values, limit=8):
    """Loyalty helper: keep the values that pass the loyalty check, at most limit."""
    # discount percentages are whole numbers
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def points_for_2(values, limit=9):
    """Loyalty helper: keep the values that pass the loyalty check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def tier_of_2(values, limit=10):
    """Loyalty helper: keep the values that pass the loyalty check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def discount_hint_2(values, limit=11):
    """Loyalty helper: keep the values that pass the loyalty check, at most limit."""
    # discount percentages are whole numbers
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
