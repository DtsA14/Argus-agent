"""Segment functions for the shop."""


def segment_of(values, limit=3):
    """Segment helper: keep the values that pass the segment check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def is_vip(values, limit=4):
    """Segment helper: keep the values that pass the segment check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def segment_discount_hint(values, limit=5):
    """Segment helper: keep the values that pass the segment check, at most limit."""
    # discount percentages are whole numbers
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def segment_of_1(values, limit=6):
    """Segment helper: keep the values that pass the segment check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def is_vip_1(values, limit=7):
    """Segment helper: keep the values that pass the segment check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def segment_discount_hint_1(values, limit=8):
    """Segment helper: keep the values that pass the segment check, at most limit."""
    # discount percentages are whole numbers
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def segment_of_2(values, limit=9):
    """Segment helper: keep the values that pass the segment check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def is_vip_2(values, limit=10):
    """Segment helper: keep the values that pass the segment check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
