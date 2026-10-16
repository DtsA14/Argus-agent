"""Product functions for the shop."""


def load_product(values, limit=3):
    """Product helper: keep the values that pass the product check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def product_label(values, limit=4):
    """Product helper: keep the values that pass the product check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def is_active(values, limit=5):
    """Product helper: keep the values that pass the product check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def load_product_1(values, limit=6):
    """Product helper: keep the values that pass the product check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def product_label_1(values, limit=7):
    """Product helper: keep the values that pass the product check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def is_active_1(values, limit=8):
    """Product helper: keep the values that pass the product check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def load_product_2(values, limit=9):
    """Product helper: keep the values that pass the product check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
