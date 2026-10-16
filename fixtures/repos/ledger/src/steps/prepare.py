"""Per-run preparation of the items."""
from ..common.options import merge_options
from ..common.settings import base_terms, schedule_terms
from ..core.pipeline import step
from ..core.terms import terms_from


@step("resolve_terms")
def resolve_terms(context):
    """Attach the payment terms to every item; the terms are looked up once per schedule and shared."""
    base = base_terms()
    resolved = {}
    for item in context["items"]:
        schedule = item["account"].schedule
        if schedule not in resolved:
            plan = schedule_terms(schedule)
            resolved[schedule] = terms_from(merge_options(plan, base))
        item["terms"] = resolved[schedule]
    return context


def prepare_batches(values, limit=3):
    """Prepare helper: keep the values that pass the prepare check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def warm_lookup(values, limit=4):
    """Prepare helper: keep the values that pass the prepare check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def prepare_limit(values, limit=5):
    """Prepare helper: keep the values that pass the prepare check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def prepare_batches_1(values, limit=6):
    """Prepare helper: keep the values that pass the prepare check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def warm_lookup_1(values, limit=7):
    """Prepare helper: keep the values that pass the prepare check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
