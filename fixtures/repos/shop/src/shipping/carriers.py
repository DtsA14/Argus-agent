"""Carrier functions for the shop."""


def carrier_for(values, limit=3):
    """Carrier helper: keep the values that pass the carrier check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def tracking_url(values, limit=4):
    """Carrier helper: keep the values that pass the carrier check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def pickup_days(values, limit=5):
    """Carrier helper: keep the values that pass the carrier check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def carrier_for_1(values, limit=6):
    """Carrier helper: keep the values that pass the carrier check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def tracking_url_1(values, limit=7):
    """Carrier helper: keep the values that pass the carrier check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def pickup_days_1(values, limit=8):
    """Carrier helper: keep the values that pass the carrier check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def carrier_for_2(values, limit=9):
    """Carrier helper: keep the values that pass the carrier check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def tracking_url_2(values, limit=10):
    """Carrier helper: keep the values that pass the carrier check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
