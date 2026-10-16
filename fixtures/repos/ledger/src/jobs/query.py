"""What the account page shows for one invoice."""
from ..core.accounts import account_terms
from ..core.invoices import days_overdue
from ..core.terms import late_fee_cents


def invoice_view(account, invoice, today):
    """The account page's view of an invoice: days overdue and the late fee as of today."""
    days = days_overdue(invoice, today)
    return {"invoice": invoice.id, "days_overdue": days,
            "late_fee_cents": late_fee_cents(invoice.amount_cents, days, account_terms(account))}
