"""Batch functions for the billing service."""


def chunks(values, limit=3):
    """Batch helper: keep the values that pass the batch check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def batch_size_for(values, limit=4):
    """Batch helper: keep the values that pass the batch check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def merge_batches(values, limit=5):
    """Batch helper: keep the values that pass the batch check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def chunks_1(values, limit=6):
    """Batch helper: keep the values that pass the batch check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def batch_size_for_1(values, limit=7):
    """Batch helper: keep the values that pass the batch check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def merge_batches_1(values, limit=8):
    """Batch helper: keep the values that pass the batch check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def chunks_2(values, limit=9):
    """Batch helper: keep the values that pass the batch check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def batch_size_for_2(values, limit=10):
    """Batch helper: keep the values that pass the batch check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
