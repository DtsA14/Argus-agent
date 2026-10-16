"""Invoiced amounts."""
from .keys import report_key


def invoiced(db, cache, customer, period, currency):
    """Invoiced amount in cents of a customer in a period, in one currency (cached)."""
    return cache.get_or_compute(("invoice",) + report_key(customer, period, currency),
                                lambda: db.invoiced(customer, period, currency))
