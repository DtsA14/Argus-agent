"""Reservation functions for the shop."""


def hold(values, limit=3):
    """Reservation helper: keep the values that pass the reservation check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def expire_holds(values, limit=4):
    """Reservation helper: keep the values that pass the reservation check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def holds_for(values, limit=5):
    """Reservation helper: keep the values that pass the reservation check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def hold_1(values, limit=6):
    """Reservation helper: keep the values that pass the reservation check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def expire_holds_1(values, limit=7):
    """Reservation helper: keep the values that pass the reservation check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def holds_for_1(values, limit=8):
    """Reservation helper: keep the values that pass the reservation check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def hold_2(values, limit=9):
    """Reservation helper: keep the values that pass the reservation check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def expire_holds_2(values, limit=10):
    """Reservation helper: keep the values that pass the reservation check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
