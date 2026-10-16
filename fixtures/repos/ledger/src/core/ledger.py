"""Ledger lines for batch processing: one line per open invoice, with terms resolved once per schedule."""
from dataclasses import dataclass

from ..common.options import merge_options
from ..common.settings import base_terms, schedule_terms
from .invoices import days_overdue
from .terms import terms_from


@dataclass(frozen=True)
class Line:
    invoice_id: str
    account_id: str
    amount_cents: int
    days_overdue: int
    terms: object


def prepare_lines(accounts, invoices, today):
    """Lines for the given invoices; the terms are looked up once per schedule and shared by its accounts."""
    by_id = {a.id: a for a in accounts}
    base = base_terms()
    resolved = {}
    lines = []
    for inv in invoices:
        account = by_id[inv.account_id]
        if account.schedule not in resolved:
            plan = schedule_terms(account.schedule)
            resolved[account.schedule] = terms_from(merge_options(plan, base))
        lines.append(Line(inv.id, account.id, inv.amount_cents, days_overdue(inv, today),
                          resolved[account.schedule]))
    return lines
