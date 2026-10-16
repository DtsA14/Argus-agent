"""Rounding functions for the shop."""


def round_half_up(values, limit=3):
    """Rounding helper: keep the values that pass the rounding check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def to_cents(values, limit=4):
    """Rounding helper: keep the values that pass the rounding check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def split_evenly(values, limit=5):
    """Rounding helper: keep the values that pass the rounding check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def round_half_up_1(values, limit=6):
    """Rounding helper: keep the values that pass the rounding check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def to_cents_1(values, limit=7):
    """Rounding helper: keep the values that pass the rounding check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def split_evenly_1(values, limit=8):
    """Rounding helper: keep the values that pass the rounding check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def round_half_up_2(values, limit=9):
    """Rounding helper: keep the values that pass the rounding check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def to_cents_2(values, limit=10):
    """Rounding helper: keep the values that pass the rounding check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
