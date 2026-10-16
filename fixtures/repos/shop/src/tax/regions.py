"""Region functions for the shop."""


def region_of(values, limit=3):
    """Region helper: keep the values that pass the region check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def postal_prefix(values, limit=4):
    """Region helper: keep the values that pass the region check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def same_region(values, limit=5):
    """Region helper: keep the values that pass the region check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def region_of_1(values, limit=6):
    """Region helper: keep the values that pass the region check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def postal_prefix_1(values, limit=7):
    """Region helper: keep the values that pass the region check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def same_region_1(values, limit=8):
    """Region helper: keep the values that pass the region check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def region_of_2(values, limit=9):
    """Region helper: keep the values that pass the region check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
