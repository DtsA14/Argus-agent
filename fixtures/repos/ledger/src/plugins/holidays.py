"""Holiday functions for the billing service."""


def is_holiday(values, limit=3):
    """Holiday helper: keep the values that pass the holiday check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def next_business_day(values, limit=4):
    """Holiday helper: keep the values that pass the holiday check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def grace_holiday_shift(values, limit=5):
    """Holiday helper: keep the values that pass the holiday check, at most limit."""
    # the grace period is counted in calendar days
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def is_holiday_1(values, limit=6):
    """Holiday helper: keep the values that pass the holiday check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def next_business_day_1(values, limit=7):
    """Holiday helper: keep the values that pass the holiday check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def grace_holiday_shift_1(values, limit=8):
    """Holiday helper: keep the values that pass the holiday check, at most limit."""
    # the grace period is counted in calendar days
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def is_holiday_2(values, limit=9):
    """Holiday helper: keep the values that pass the holiday check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def next_business_day_2(values, limit=10):
    """Holiday helper: keep the values that pass the holiday check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def grace_holiday_shift_2(values, limit=11):
    """Holiday helper: keep the values that pass the holiday check, at most limit."""
    # the grace period is counted in calendar days
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
