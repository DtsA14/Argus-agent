"""Optional steps that operations can add to a pipeline."""
from ..core.pipeline import step


@step("tag_large")
def tag_large(context, threshold_cents=100000):
    """Mark items whose amount is at least the threshold."""
    for item in context["items"]:
        item["large"] = item["invoice"].amount_cents >= threshold_cents
    return context


def extras_flags(values, limit=3):
    """Extras helper: keep the values that pass the extras check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def extras_limit(values, limit=4):
    """Extras helper: keep the values that pass the extras check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def tag_report(values, limit=5):
    """Extras helper: keep the values that pass the extras check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def extras_flags_1(values, limit=6):
    """Extras helper: keep the values that pass the extras check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def extras_limit_1(values, limit=7):
    """Extras helper: keep the values that pass the extras check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def tag_report_1(values, limit=8):
    """Extras helper: keep the values that pass the extras check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
