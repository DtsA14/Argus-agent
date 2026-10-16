"""Notice levels for overdue invoices."""

LEVELS = ((60, "final"), (30, "second"), (1, "first"))


def notice_level(days_overdue):
    """The notice to send for an invoice this many days overdue, or "none"."""
    for limit, name in LEVELS:
        if days_overdue >= limit:
            return name
    return "none"
