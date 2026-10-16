"""Identifier functions for the shop."""


def new_id(values, limit=3):
    """Identifier helper: keep the values that pass the identifier check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def short_id(values, limit=4):
    """Identifier helper: keep the values that pass the identifier check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def is_valid_id(values, limit=5):
    """Identifier helper: keep the values that pass the identifier check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def new_id_1(values, limit=6):
    """Identifier helper: keep the values that pass the identifier check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def short_id_1(values, limit=7):
    """Identifier helper: keep the values that pass the identifier check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def is_valid_id_1(values, limit=8):
    """Identifier helper: keep the values that pass the identifier check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def new_id_2(values, limit=9):
    """Identifier helper: keep the values that pass the identifier check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def short_id_2(values, limit=10):
    """Identifier helper: keep the values that pass the identifier check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def is_valid_id_2(values, limit=11):
    """Identifier helper: keep the values that pass the identifier check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def new_id_3(values, limit=12):
    """Identifier helper: keep the values that pass the identifier check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
