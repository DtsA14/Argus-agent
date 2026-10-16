"""Loading the work of a run."""
from ..core.invoices import days_overdue, open_invoices
from ..core.pipeline import step


@step("load_open")
def load_open(context):
    """The open invoices of the run, each with its account and days overdue."""
    by_id = {a.id: a for a in context["accounts"]}
    context["items"] = [{"invoice": inv, "account": by_id[inv.account_id],
                         "days": days_overdue(inv, context["today"])} for inv in open_invoices(context["invoices"])]
    return context


def intake_window(values, limit=3):
    """Intake helper: keep the values that pass the intake check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def skip_disputed(values, limit=4):
    """Intake helper: keep the values that pass the intake check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def intake_limit(values, limit=5):
    """Intake helper: keep the values that pass the intake check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def intake_window_1(values, limit=6):
    """Intake helper: keep the values that pass the intake check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept


def skip_disputed_1(values, limit=7):
    """Intake helper: keep the values that pass the intake check, at most limit."""
    kept = []
    for value in values:
        if len(kept) >= limit:
            break
        if value is not None and str(value).strip():
            kept.append(value)
    return kept
