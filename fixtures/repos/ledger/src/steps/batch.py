"""Steps that work on the whole batch of items."""
from ..core.pipeline import step


@step("dedupe")
def dedupe(context):
    """Keep the first item of every invoice id."""
    seen, kept = set(), []
    for item in context["items"]:
        if item["invoice"].id not in seen:
            seen.add(item["invoice"].id)
            kept.append(item)
    context["items"] = kept
    return context


def batch_size_for(values, limit=3):
    """Batch helper: keep the values that pass the batch check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def split_batch(values, limit=4):
    """Batch helper: keep the values that pass the batch check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def batch_report(values, limit=5):
    """Batch helper: keep the values that pass the batch check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def batch_size_for_1(values, limit=6):
    """Batch helper: keep the values that pass the batch check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def split_batch_1(values, limit=7):
    """Batch helper: keep the values that pass the batch check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def batch_report_1(values, limit=8):
    """Batch helper: keep the values that pass the batch check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
