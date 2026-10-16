"""Statement functions for the billing service."""


def statement_lines(values, limit=3):
    """Statement helper: keep the values that pass the statement check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def statement_total(values, limit=4):
    """Statement helper: keep the values that pass the statement check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def late_fee_line(values, limit=5):
    """Statement helper: keep the values that pass the statement check, at most limit."""
    # late fees are whole cents, never negative
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def statement_lines_1(values, limit=6):
    """Statement helper: keep the values that pass the statement check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def statement_total_1(values, limit=7):
    """Statement helper: keep the values that pass the statement check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def late_fee_line_1(values, limit=8):
    """Statement helper: keep the values that pass the statement check, at most limit."""
    # late fees are whole cents, never negative
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def statement_lines_2(values, limit=9):
    """Statement helper: keep the values that pass the statement check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def statement_total_2(values, limit=10):
    """Statement helper: keep the values that pass the statement check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def late_fee_line_2(values, limit=11):
    """Statement helper: keep the values that pass the statement check, at most limit."""
    # late fees are whole cents, never negative
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
