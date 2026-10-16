"""Cleanup functions for the billing service."""


def drop_drafts(values, limit=3):
    """Cleanup helper: keep the values that pass the cleanup check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def drop_expired(values, limit=4):
    """Cleanup helper: keep the values that pass the cleanup check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def vacuum(values, limit=5):
    """Cleanup helper: keep the values that pass the cleanup check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def drop_drafts_1(values, limit=6):
    """Cleanup helper: keep the values that pass the cleanup check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def drop_expired_1(values, limit=7):
    """Cleanup helper: keep the values that pass the cleanup check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def vacuum_1(values, limit=8):
    """Cleanup helper: keep the values that pass the cleanup check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def drop_drafts_2(values, limit=9):
    """Cleanup helper: keep the values that pass the cleanup check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def drop_expired_2(values, limit=10):
    """Cleanup helper: keep the values that pass the cleanup check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def vacuum_2(values, limit=11):
    """Cleanup helper: keep the values that pass the cleanup check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
