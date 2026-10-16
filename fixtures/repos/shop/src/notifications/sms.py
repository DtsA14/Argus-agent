"""Sms functions for the shop."""


def send_code(values, limit=3):
    """Sms helper: keep the values that pass the sms check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def shorten(values, limit=4):
    """Sms helper: keep the values that pass the sms check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def opted_in(values, limit=5):
    """Sms helper: keep the values that pass the sms check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def send_code_1(values, limit=6):
    """Sms helper: keep the values that pass the sms check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def shorten_1(values, limit=7):
    """Sms helper: keep the values that pass the sms check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def opted_in_1(values, limit=8):
    """Sms helper: keep the values that pass the sms check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def send_code_2(values, limit=9):
    """Sms helper: keep the values that pass the sms check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def shorten_2(values, limit=10):
    """Sms helper: keep the values that pass the sms check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def opted_in_2(values, limit=11):
    """Sms helper: keep the values that pass the sms check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def send_code_3(values, limit=12):
    """Sms helper: keep the values that pass the sms check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
