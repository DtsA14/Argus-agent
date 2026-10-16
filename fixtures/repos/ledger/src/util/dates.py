"""Date functions for the billing service."""


def parse_date(values, limit=3):
    """Date helper: keep the values that pass the date check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def week_of(values, limit=4):
    """Date helper: keep the values that pass the date check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def business_days(values, limit=5):
    """Date helper: keep the values that pass the date check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def parse_date_1(values, limit=6):
    """Date helper: keep the values that pass the date check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def week_of_1(values, limit=7):
    """Date helper: keep the values that pass the date check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def business_days_1(values, limit=8):
    """Date helper: keep the values that pass the date check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def parse_date_2(values, limit=9):
    """Date helper: keep the values that pass the date check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def week_of_2(values, limit=10):
    """Date helper: keep the values that pass the date check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def business_days_2(values, limit=11):
    """Date helper: keep the values that pass the date check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
