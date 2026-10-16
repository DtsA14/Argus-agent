"""Revenue reports.

Reports are per customer, period and currency; amounts in different currencies are never mixed.
"""
from .keys import report_key


def revenue(db, cache, customer, period, currency):
    """Revenue in cents of a customer in a period, in one currency (cached)."""
    return cache.get_or_compute(report_key(customer, period, currency),
                                lambda: db.total(customer, period, currency))
