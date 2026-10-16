"""The overnight run: assess late fees on open invoices and produce one row per invoice for the export file."""
from ..adapters.rows import row
from ..core.invoices import open_invoices
from ..core.ledger import prepare_lines
from ..core.terms import late_fee_cents
from ..plugins.notices import notice_level


def run_cycle(accounts, invoices, today):
    """Rows for every open invoice: invoice, account, days overdue, late fee and notice level."""
    out = []
    for line in prepare_lines(accounts, open_invoices(invoices), today):
        fee = late_fee_cents(line.amount_cents, line.days_overdue, line.terms)
        out.append(row(line.invoice_id, line.account_id, line.days_overdue, fee, notice_level(line.days_overdue)))
    return out
