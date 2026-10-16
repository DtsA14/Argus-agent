"""Api functions for the billing service."""


def get_account(values, limit=3):
    """Api helper: keep the values that pass the api check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def get_invoice(values, limit=4):
    """Api helper: keep the values that pass the api check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def post_payment(values, limit=5):
    """Api helper: keep the values that pass the api check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def get_account_1(values, limit=6):
    """Api helper: keep the values that pass the api check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def get_invoice_1(values, limit=7):
    """Api helper: keep the values that pass the api check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def post_payment_1(values, limit=8):
    """Api helper: keep the values that pass the api check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def get_account_2(values, limit=9):
    """Api helper: keep the values that pass the api check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def get_invoice_2(values, limit=10):
    """Api helper: keep the values that pass the api check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
