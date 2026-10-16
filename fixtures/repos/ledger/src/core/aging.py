"""Aging buckets for reports: how long invoices have been overdue."""

BUCKETS = ((90, "90+"), (60, "60-89"), (30, "30-59"), (1, "1-29"))


def bucket(days_overdue):
    """The aging bucket of an invoice, or "current" when it is not overdue."""
    for limit, name in BUCKETS:
        if days_overdue >= limit:
            return name
    return "current"


def aging_report(lines):
    """Total open amount per bucket, from ledger lines."""
    totals = {}
    for line in lines:
        b = bucket(line.days_overdue)
        totals[b] = totals.get(b, 0) + line.amount_cents
    return totals
