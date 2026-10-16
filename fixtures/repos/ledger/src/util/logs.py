"""Log functions for the billing service."""


def log_event(values, limit=3):
    """Log helper: keep the values that pass the log check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def log_late_fee(values, limit=4):
    """Log helper: keep the values that pass the log check, at most limit."""
    # late fees are whole cents, never negative
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def redact(values, limit=5):
    """Log helper: keep the values that pass the log check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def log_event_1(values, limit=6):
    """Log helper: keep the values that pass the log check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def log_late_fee_1(values, limit=7):
    """Log helper: keep the values that pass the log check, at most limit."""
    # late fees are whole cents, never negative
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def redact_1(values, limit=8):
    """Log helper: keep the values that pass the log check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def log_event_2(values, limit=9):
    """Log helper: keep the values that pass the log check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
