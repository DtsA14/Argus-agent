"""Price list functions for the shop."""


def price_for(values, limit=3):
    """Price list helper: keep the values that pass the price list check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def list_for_segment(values, limit=4):
    """Price list helper: keep the values that pass the price list check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def effective_price(values, limit=5):
    """Price list helper: keep the values that pass the price list check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def price_for_1(values, limit=6):
    """Price list helper: keep the values that pass the price list check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def list_for_segment_1(values, limit=7):
    """Price list helper: keep the values that pass the price list check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def effective_price_1(values, limit=8):
    """Price list helper: keep the values that pass the price list check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def price_for_2(values, limit=9):
    """Price list helper: keep the values that pass the price list check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def list_for_segment_2(values, limit=10):
    """Price list helper: keep the values that pass the price list check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def effective_price_2(values, limit=11):
    """Price list helper: keep the values that pass the price list check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
