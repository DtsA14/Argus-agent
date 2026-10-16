"""Steps kept for pipelines migrated from the old billing system (not in any current pipeline)."""
from ..common.settings import base_terms
from ..core.pipeline import step
from ..core.terms import terms_from


@step("resolve_terms_v1")
def resolve_terms_v1(context):
    """The old behaviour: every item gets the base terms, whatever its schedule."""
    terms = terms_from(base_terms())
    for item in context["items"]:
        item["terms"] = terms
    return context


def legacy_codes(values, limit=3):
    """Compat helper: keep the values that pass the compat check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def compat_limit(values, limit=4):
    """Compat helper: keep the values that pass the compat check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def map_old_schedule(values, limit=5):
    """Compat helper: keep the values that pass the compat check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def legacy_codes_1(values, limit=6):
    """Compat helper: keep the values that pass the compat check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def compat_limit_1(values, limit=7):
    """Compat helper: keep the values that pass the compat check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
