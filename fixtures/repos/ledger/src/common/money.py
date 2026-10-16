"""Money functions for the billing service."""


def format_cents(values, limit=3):
    """Money helper: keep the values that pass the money check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def parse_cents(values, limit=4):
    """Money helper: keep the values that pass the money check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def sum_cents(values, limit=5):
    """Money helper: keep the values that pass the money check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def format_cents_1(values, limit=6):
    """Money helper: keep the values that pass the money check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def parse_cents_1(values, limit=7):
    """Money helper: keep the values that pass the money check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def sum_cents_1(values, limit=8):
    """Money helper: keep the values that pass the money check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def format_cents_2(values, limit=9):
    """Money helper: keep the values that pass the money check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
