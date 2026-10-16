"""Reminder messages for invoices close to the end of their grace period."""
from ..common.options import merge_options
from ..common.settings import base_terms, schedule_terms
from ..core.invoices import days_overdue
from ..core.terms import terms_from

REMIND_BEFORE_DAYS = 3


def due_for_reminder(account, invoice, today):
    """True when the grace period of the invoice ends within the next few days."""
    terms = terms_from(merge_options(base_terms(), schedule_terms(account.schedule)))
    left = terms.grace_days - days_overdue(invoice, today)
    return 0 <= left <= REMIND_BEFORE_DAYS


def reminder_text(account, invoice):
    """The text of a reminder (no amounts: those are on the account page)."""
    return f"Dear {account.name}, invoice {invoice.id} is overdue. A late fee applies after the grace period."
