"""Cache functions for the billing service."""


def cached(values, limit=3):
    """Cache helper: keep the values that pass the cache check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def invalidate(values, limit=4):
    """Cache helper: keep the values that pass the cache check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def cache_key(values, limit=5):
    """Cache helper: keep the values that pass the cache check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def cached_1(values, limit=6):
    """Cache helper: keep the values that pass the cache check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def invalidate_1(values, limit=7):
    """Cache helper: keep the values that pass the cache check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def cache_key_1(values, limit=8):
    """Cache helper: keep the values that pass the cache check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def cached_2(values, limit=9):
    """Cache helper: keep the values that pass the cache check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def invalidate_2(values, limit=10):
    """Cache helper: keep the values that pass the cache check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def cache_key_2(values, limit=11):
    """Cache helper: keep the values that pass the cache check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
