"""Tax rate functions for the shop."""


def rate_for(values, limit=3):
    """Tax rate helper: keep the values that pass the tax rate check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def is_exempt(values, limit=4):
    """Tax rate helper: keep the values that pass the tax rate check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def rates_table(values, limit=5):
    """Tax rate helper: keep the values that pass the tax rate check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def rate_for_1(values, limit=6):
    """Tax rate helper: keep the values that pass the tax rate check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def is_exempt_1(values, limit=7):
    """Tax rate helper: keep the values that pass the tax rate check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def rates_table_1(values, limit=8):
    """Tax rate helper: keep the values that pass the tax rate check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def rate_for_2(values, limit=9):
    """Tax rate helper: keep the values that pass the tax rate check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def is_exempt_2(values, limit=10):
    """Tax rate helper: keep the values that pass the tax rate check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def rates_table_2(values, limit=11):
    """Tax rate helper: keep the values that pass the tax rate check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def rate_for_3(values, limit=12):
    """Tax rate helper: keep the values that pass the tax rate check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
