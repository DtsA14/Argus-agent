"""Category functions for the shop."""


def category_path(values, limit=3):
    """Category helper: keep the values that pass the category check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def parent_of(values, limit=4):
    """Category helper: keep the values that pass the category check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def children_of(values, limit=5):
    """Category helper: keep the values that pass the category check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def category_path_1(values, limit=6):
    """Category helper: keep the values that pass the category check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def parent_of_1(values, limit=7):
    """Category helper: keep the values that pass the category check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def children_of_1(values, limit=8):
    """Category helper: keep the values that pass the category check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def category_path_2(values, limit=9):
    """Category helper: keep the values that pass the category check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
