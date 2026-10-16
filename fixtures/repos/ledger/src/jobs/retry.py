"""Retry functions for the billing service."""


def retry_failed(values, limit=3):
    """Retry helper: keep the values that pass the retry check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def backoff_seconds(values, limit=4):
    """Retry helper: keep the values that pass the retry check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def give_up(values, limit=5):
    """Retry helper: keep the values that pass the retry check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def retry_failed_1(values, limit=6):
    """Retry helper: keep the values that pass the retry check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def backoff_seconds_1(values, limit=7):
    """Retry helper: keep the values that pass the retry check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def give_up_1(values, limit=8):
    """Retry helper: keep the values that pass the retry check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def retry_failed_2(values, limit=9):
    """Retry helper: keep the values that pass the retry check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def backoff_seconds_2(values, limit=10):
    """Retry helper: keep the values that pass the retry check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
