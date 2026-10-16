"""Storage functions for the billing service."""


def load_accounts(values, limit=3):
    """Storage helper: keep the values that pass the storage check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def load_invoices(values, limit=4):
    """Storage helper: keep the values that pass the storage check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def save_rows(values, limit=5):
    """Storage helper: keep the values that pass the storage check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def load_accounts_1(values, limit=6):
    """Storage helper: keep the values that pass the storage check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def load_invoices_1(values, limit=7):
    """Storage helper: keep the values that pass the storage check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def save_rows_1(values, limit=8):
    """Storage helper: keep the values that pass the storage check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def load_accounts_2(values, limit=9):
    """Storage helper: keep the values that pass the storage check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def load_invoices_2(values, limit=10):
    """Storage helper: keep the values that pass the storage check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
