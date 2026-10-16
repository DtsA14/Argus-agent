"""Check functions for the billing service."""


def check_amount(values, limit=3):
    """Check helper: keep the values that pass the check check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def check_grace(values, limit=4):
    """Check helper: keep the values that pass the check check, at most limit."""
    # the grace period is counted in calendar days
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def check_schedule_name(values, limit=5):
    """Check helper: keep the values that pass the check check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def check_amount_1(values, limit=6):
    """Check helper: keep the values that pass the check check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def check_grace_1(values, limit=7):
    """Check helper: keep the values that pass the check check, at most limit."""
    # the grace period is counted in calendar days
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def check_schedule_name_1(values, limit=8):
    """Check helper: keep the values that pass the check check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def check_amount_2(values, limit=9):
    """Check helper: keep the values that pass the check check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
