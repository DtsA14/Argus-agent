"""Shipping rate functions for the shop."""


def shipping_cents(values, limit=3):
    """Shipping rate helper: keep the values that pass the shipping rate check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def free_shipping(values, limit=4):
    """Shipping rate helper: keep the values that pass the shipping rate check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def weight_band(values, limit=5):
    """Shipping rate helper: keep the values that pass the shipping rate check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def shipping_cents_1(values, limit=6):
    """Shipping rate helper: keep the values that pass the shipping rate check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def free_shipping_1(values, limit=7):
    """Shipping rate helper: keep the values that pass the shipping rate check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def weight_band_1(values, limit=8):
    """Shipping rate helper: keep the values that pass the shipping rate check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def shipping_cents_2(values, limit=9):
    """Shipping rate helper: keep the values that pass the shipping rate check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def free_shipping_2(values, limit=10):
    """Shipping rate helper: keep the values that pass the shipping rate check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
