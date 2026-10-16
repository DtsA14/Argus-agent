"""The reporting API used by the web front end."""
from . import fmt
from .cache import Cache
from .db import Database
from .invoices import invoiced
from .reports import revenue


class App:
    def __init__(self, db=None, cache=None):
        self.db = db if db is not None else Database()
        self.cache = cache if cache is not None else Cache()

    def get_report(self, customer, period, currency):
        """Revenue, invoiced and open amounts of a customer in a period, in the requested currency."""
        rev = revenue(self.db, self.cache, customer, period, currency)
        inv = invoiced(self.db, self.cache, customer, period, currency)
        return {"currency": currency, "revenue": fmt.amount(rev, currency),
                "invoiced": fmt.amount(inv, currency), "open": fmt.amount(rev - inv, currency)}
