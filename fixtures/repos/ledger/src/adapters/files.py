"""File functions for the billing service."""


def write_lines(values, limit=3):
    """File helper: keep the values that pass the file check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def rotate(values, limit=4):
    """File helper: keep the values that pass the file check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def file_name_for(values, limit=5):
    """File helper: keep the values that pass the file check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def write_lines_1(values, limit=6):
    """File helper: keep the values that pass the file check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def rotate_1(values, limit=7):
    """File helper: keep the values that pass the file check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def file_name_for_1(values, limit=8):
    """File helper: keep the values that pass the file check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def write_lines_2(values, limit=9):
    """File helper: keep the values that pass the file check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def rotate_2(values, limit=10):
    """File helper: keep the values that pass the file check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def file_name_for_2(values, limit=11):
    """File helper: keep the values that pass the file check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
