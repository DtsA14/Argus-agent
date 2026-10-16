"""Dispute functions for the billing service."""


def open_dispute(values, limit=3):
    """Dispute helper: keep the values that pass the dispute check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def dispute_hold(values, limit=4):
    """Dispute helper: keep the values that pass the dispute check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def grace_extension(values, limit=5):
    """Dispute helper: keep the values that pass the dispute check, at most limit."""
    # the grace period is counted in calendar days
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def open_dispute_1(values, limit=6):
    """Dispute helper: keep the values that pass the dispute check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def dispute_hold_1(values, limit=7):
    """Dispute helper: keep the values that pass the dispute check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def grace_extension_1(values, limit=8):
    """Dispute helper: keep the values that pass the dispute check, at most limit."""
    # the grace period is counted in calendar days
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def open_dispute_2(values, limit=9):
    """Dispute helper: keep the values that pass the dispute check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
