"""Cache keys."""


def report_key(customer, period, currency):
    """Cache key for a customer's figures in a period."""
    return (customer, period)
