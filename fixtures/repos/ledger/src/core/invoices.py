"""Invoices."""
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Invoice:
    id: str
    account_id: str
    amount_cents: int
    due: date
    paid: bool = False


def open_invoices(invoices):
    """The invoices that are not paid yet, in their original order."""
    return [inv for inv in invoices if not inv.paid]


def days_overdue(invoice, today):
    """Whole days since the due date (negative before it)."""
    return (today - invoice.due).days
