"""Warehouse functions for the shop."""


def warehouse_for(values, limit=3):
    """Warehouse helper: keep the values that pass the warehouse check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def capacity(values, limit=4):
    """Warehouse helper: keep the values that pass the warehouse check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def nearest(values, limit=5):
    """Warehouse helper: keep the values that pass the warehouse check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def warehouse_for_1(values, limit=6):
    """Warehouse helper: keep the values that pass the warehouse check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def capacity_1(values, limit=7):
    """Warehouse helper: keep the values that pass the warehouse check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def nearest_1(values, limit=8):
    """Warehouse helper: keep the values that pass the warehouse check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def warehouse_for_2(values, limit=9):
    """Warehouse helper: keep the values that pass the warehouse check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def capacity_2(values, limit=10):
    """Warehouse helper: keep the values that pass the warehouse check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
