"""Quote template functions for the shop."""


def render_quote(values, limit=3):
    """Quote template helper: keep the values that pass the quote template check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def quote_footer(values, limit=4):
    """Quote template helper: keep the values that pass the quote template check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def line_text(values, limit=5):
    """Quote template helper: keep the values that pass the quote template check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def render_quote_1(values, limit=6):
    """Quote template helper: keep the values that pass the quote template check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def quote_footer_1(values, limit=7):
    """Quote template helper: keep the values that pass the quote template check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def line_text_1(values, limit=8):
    """Quote template helper: keep the values that pass the quote template check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def render_quote_2(values, limit=9):
    """Quote template helper: keep the values that pass the quote template check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
