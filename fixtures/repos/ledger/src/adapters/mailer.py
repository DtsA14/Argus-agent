"""Mail functions for the billing service."""


def send_notice(values, limit=3):
    """Mail helper: keep the values that pass the mail check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def send_receipt(values, limit=4):
    """Mail helper: keep the values that pass the mail check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def late_fee_mail(values, limit=5):
    """Mail helper: keep the values that pass the mail check, at most limit."""
    # late fees are whole cents, never negative
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def send_notice_1(values, limit=6):
    """Mail helper: keep the values that pass the mail check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def send_receipt_1(values, limit=7):
    """Mail helper: keep the values that pass the mail check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def late_fee_mail_1(values, limit=8):
    """Mail helper: keep the values that pass the mail check, at most limit."""
    # late fees are whole cents, never negative
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def send_notice_2(values, limit=9):
    """Mail helper: keep the values that pass the mail check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
