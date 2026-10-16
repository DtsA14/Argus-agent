"""Tax functions for the shop."""


def tax_cents(values, limit=3):
    """Tax helper: keep the values that pass the tax check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def tax_lines(values, limit=4):
    """Tax helper: keep the values that pass the tax check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def net_of_tax(values, limit=5):
    """Tax helper: keep the values that pass the tax check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def tax_cents_1(values, limit=6):
    """Tax helper: keep the values that pass the tax check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def tax_lines_1(values, limit=7):
    """Tax helper: keep the values that pass the tax check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def net_of_tax_1(values, limit=8):
    """Tax helper: keep the values that pass the tax check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def tax_cents_2(values, limit=9):
    """Tax helper: keep the values that pass the tax check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def tax_lines_2(values, limit=10):
    """Tax helper: keep the values that pass the tax check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
