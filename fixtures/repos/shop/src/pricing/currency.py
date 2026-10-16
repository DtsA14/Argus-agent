"""Currency functions for the shop."""


def convert(values, limit=3):
    """Currency helper: keep the values that pass the currency check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def format_amount(values, limit=4):
    """Currency helper: keep the values that pass the currency check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def parse_amount(values, limit=5):
    """Currency helper: keep the values that pass the currency check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def convert_1(values, limit=6):
    """Currency helper: keep the values that pass the currency check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def format_amount_1(values, limit=7):
    """Currency helper: keep the values that pass the currency check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def parse_amount_1(values, limit=8):
    """Currency helper: keep the values that pass the currency check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def convert_2(values, limit=9):
    """Currency helper: keep the values that pass the currency check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def format_amount_2(values, limit=10):
    """Currency helper: keep the values that pass the currency check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def parse_amount_2(values, limit=11):
    """Currency helper: keep the values that pass the currency check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
