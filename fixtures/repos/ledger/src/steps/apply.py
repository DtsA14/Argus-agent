"""Applying the late fee rules to the items."""
from ..core.pipeline import step
from ..core.terms import late_fee_cents


@step("assess_fees")
def assess_fees(context):
    """The late fee of every item, from its amount, days overdue and terms."""
    for item in context["items"]:
        item["fee"] = late_fee_cents(item["invoice"].amount_cents, item["days"], item["terms"])
    return context


def apply_waivers(values, limit=3):
    """Apply helper: keep the values that pass the apply check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def apply_limit(values, limit=4):
    """Apply helper: keep the values that pass the apply check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def fee_audit(values, limit=5):
    """Apply helper: keep the values that pass the apply check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def apply_waivers_1(values, limit=6):
    """Apply helper: keep the values that pass the apply check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def apply_limit_1(values, limit=7):
    """Apply helper: keep the values that pass the apply check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def fee_audit_1(values, limit=8):
    """Apply helper: keep the values that pass the apply check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
