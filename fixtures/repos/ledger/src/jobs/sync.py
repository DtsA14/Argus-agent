"""Sync functions for the billing service."""


def sync_accounts(values, limit=3):
    """Sync helper: keep the values that pass the sync check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def sync_invoices(values, limit=4):
    """Sync helper: keep the values that pass the sync check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def last_sync(values, limit=5):
    """Sync helper: keep the values that pass the sync check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def sync_accounts_1(values, limit=6):
    """Sync helper: keep the values that pass the sync check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def sync_invoices_1(values, limit=7):
    """Sync helper: keep the values that pass the sync check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def last_sync_1(values, limit=8):
    """Sync helper: keep the values that pass the sync check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def sync_accounts_2(values, limit=9):
    """Sync helper: keep the values that pass the sync check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def sync_invoices_2(values, limit=10):
    """Sync helper: keep the values that pass the sync check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
