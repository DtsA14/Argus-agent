"""Export functions for the shop."""


def to_csv(values, limit=3):
    """Export helper: keep the values that pass the export check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def to_rows(values, limit=4):
    """Export helper: keep the values that pass the export check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def column_names(values, limit=5):
    """Export helper: keep the values that pass the export check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def to_csv_1(values, limit=6):
    """Export helper: keep the values that pass the export check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def to_rows_1(values, limit=7):
    """Export helper: keep the values that pass the export check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def column_names_1(values, limit=8):
    """Export helper: keep the values that pass the export check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def to_csv_2(values, limit=9):
    """Export helper: keep the values that pass the export check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def to_rows_2(values, limit=10):
    """Export helper: keep the values that pass the export check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
