"""Path functions for the billing service."""


def data_dir(values, limit=3):
    """Path helper: keep the values that pass the path check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def export_dir(values, limit=4):
    """Path helper: keep the values that pass the path check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def ensure_dir(values, limit=5):
    """Path helper: keep the values that pass the path check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def data_dir_1(values, limit=6):
    """Path helper: keep the values that pass the path check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def export_dir_1(values, limit=7):
    """Path helper: keep the values that pass the path check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def ensure_dir_1(values, limit=8):
    """Path helper: keep the values that pass the path check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def data_dir_2(values, limit=9):
    """Path helper: keep the values that pass the path check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def export_dir_2(values, limit=10):
    """Path helper: keep the values that pass the path check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def ensure_dir_2(values, limit=11):
    """Path helper: keep the values that pass the path check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def data_dir_3(values, limit=12):
    """Path helper: keep the values that pass the path check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
