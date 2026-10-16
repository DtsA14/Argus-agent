"""Rows of the export file."""

COLUMNS = ("invoice", "account", "days_overdue", "late_fee_cents", "notice")


def row(invoice_id, account_id, days, fee_cents, notice):
    """One row as a dict with the export columns."""
    return dict(zip(COLUMNS, (invoice_id, account_id, days, fee_cents, notice)))


def to_line(r, sep=";"):
    """A row as one line of text, in column order."""
    return sep.join(str(r[c]) for c in COLUMNS)
