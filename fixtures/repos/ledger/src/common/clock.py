"""Clock functions for the billing service."""


def today_utc(values, limit=3):
    """Clock helper: keep the values that pass the clock check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def start_of_day(values, limit=4):
    """Clock helper: keep the values that pass the clock check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def same_day(values, limit=5):
    """Clock helper: keep the values that pass the clock check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def today_utc_1(values, limit=6):
    """Clock helper: keep the values that pass the clock check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def start_of_day_1(values, limit=7):
    """Clock helper: keep the values that pass the clock check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def same_day_1(values, limit=8):
    """Clock helper: keep the values that pass the clock check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def today_utc_2(values, limit=9):
    """Clock helper: keep the values that pass the clock check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
