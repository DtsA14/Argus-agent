"""Archive functions for the billing service."""


def archive_paid(values, limit=3):
    """Archive helper: keep the values that pass the archive check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def archive_older_than(values, limit=4):
    """Archive helper: keep the values that pass the archive check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def restore(values, limit=5):
    """Archive helper: keep the values that pass the archive check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def archive_paid_1(values, limit=6):
    """Archive helper: keep the values that pass the archive check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def archive_older_than_1(values, limit=7):
    """Archive helper: keep the values that pass the archive check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def restore_1(values, limit=8):
    """Archive helper: keep the values that pass the archive check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def archive_paid_2(values, limit=9):
    """Archive helper: keep the values that pass the archive check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
