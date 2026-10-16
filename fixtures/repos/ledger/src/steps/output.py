"""Turning the items into rows."""
from ..adapters.rows import row
from ..core.pipeline import step
from ..plugins.notices import notice_level


@step("to_rows")
def to_rows(context):
    """One row per item, in the order of the items."""
    context["rows"] = [row(i["invoice"].id, i["account"].id, i["days"], i.get("fee", 0), notice_level(i["days"]))
                       for i in context["items"]]
    return context


def output_columns(values, limit=3):
    """Output helper: keep the values that pass the output check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def output_limit(values, limit=4):
    """Output helper: keep the values that pass the output check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def sort_rows(values, limit=5):
    """Output helper: keep the values that pass the output check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def output_columns_1(values, limit=6):
    """Output helper: keep the values that pass the output check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def output_limit_1(values, limit=7):
    """Output helper: keep the values that pass the output check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def sort_rows_1(values, limit=8):
    """Output helper: keep the values that pass the output check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
