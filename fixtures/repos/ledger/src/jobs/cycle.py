"""The overnight run: assess late fees on open invoices and produce one row per invoice for the export file."""
from ..core.pipeline import run_pipeline


def run_cycle(accounts, invoices, today):
    """Rows for every open invoice: invoice, account, days overdue, late fee and notice level."""
    context = {"accounts": list(accounts), "invoices": list(invoices), "today": today}
    return run_pipeline("overnight", context)["rows"]
