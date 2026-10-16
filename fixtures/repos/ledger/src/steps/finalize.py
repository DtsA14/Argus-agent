"""Steps that run at the end of a statement run."""
from ..core.pipeline import step


@step("round_amounts")
def round_amounts(context):
    """Round every item's amount down to whole units of 100 cents for statements."""
    for item in context["items"]:
        item["rounded"] = item["invoice"].amount_cents - item["invoice"].amount_cents % 100
    return context


def finalize_totals(values, limit=3):
    """Finalize helper: keep the values that pass the finalize check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def finalize_limit(values, limit=4):
    """Finalize helper: keep the values that pass the finalize check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def close_run(values, limit=5):
    """Finalize helper: keep the values that pass the finalize check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def finalize_totals_1(values, limit=6):
    """Finalize helper: keep the values that pass the finalize check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def finalize_limit_1(values, limit=7):
    """Finalize helper: keep the values that pass the finalize check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def close_run_1(values, limit=8):
    """Finalize helper: keep the values that pass the finalize check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
