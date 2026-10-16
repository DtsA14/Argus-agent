"""Daily report functions for the shop."""


def summary_for(values, limit=3):
    """Daily report helper: keep the values that pass the daily report check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def top_products(values, limit=4):
    """Daily report helper: keep the values that pass the daily report check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def returns_for(values, limit=5):
    """Daily report helper: keep the values that pass the daily report check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def summary_for_1(values, limit=6):
    """Daily report helper: keep the values that pass the daily report check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def top_products_1(values, limit=7):
    """Daily report helper: keep the values that pass the daily report check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def returns_for_1(values, limit=8):
    """Daily report helper: keep the values that pass the daily report check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def summary_for_2(values, limit=9):
    """Daily report helper: keep the values that pass the daily report check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
