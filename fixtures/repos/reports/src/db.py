"""Orders and invoices, kept in memory. Every total() or invoiced() call counts as one query."""

ORDERS = [
    ("acme", "2026-09", "EUR", 120000),
    ("acme", "2026-09", "EUR", 4550),
    ("acme", "2026-09", "USD", 98000),
    ("acme", "2026-09", "USD", 1999),
    ("acme", "2026-10", "EUR", 5000),
    ("bolt", "2026-09", "USD", 7700),
]

INVOICES = [
    ("acme", "2026-09", "EUR", 100000),
    ("acme", "2026-09", "USD", 50000),
    ("bolt", "2026-09", "USD", 7700),
]


class Database:
    def __init__(self, orders=ORDERS, invoices=INVOICES):
        self._orders, self._invoices = list(orders), list(invoices)
        self.queries = 0

    def total(self, customer, period, currency):
        """Sum of the order amounts (cents) of a customer in a period, in one currency."""
        self.queries += 1
        return sum(c for who, when, cur, c in self._orders if (who, when, cur) == (customer, period, currency))

    def invoiced(self, customer, period, currency):
        """Sum of the invoiced amounts (cents) of a customer in a period, in one currency."""
        self.queries += 1
        return sum(c for who, when, cur, c in self._invoices if (who, when, cur) == (customer, period, currency))
