import unittest

from src.api import App
from src.invoices import invoiced

# acme, 2026-09: revenue EUR 124550 / USD 99999 cents; invoiced EUR 100000 / USD 50000 cents (written out, not computed).
EUR = {"currency": "EUR", "revenue": "EUR 1245.50", "invoiced": "EUR 1000.00", "open": "EUR 245.50"}
USD = {"currency": "USD", "revenue": "USD 999.99", "invoiced": "USD 500.00", "open": "USD 499.99"}


class CurrenciesTest(unittest.TestCase):
    def test_report_eur_then_usd(self):
        app = App()
        self.assertEqual(app.get_report("acme", "2026-09", "EUR"), EUR)
        self.assertEqual(app.get_report("acme", "2026-09", "USD"), USD)

    def test_report_usd_then_eur(self):
        app = App()
        self.assertEqual(app.get_report("acme", "2026-09", "USD"), USD)
        self.assertEqual(app.get_report("acme", "2026-09", "EUR"), EUR)

    def test_invoiced_eur_then_usd(self):
        app = App()
        self.assertEqual(invoiced(app.db, app.cache, "acme", "2026-09", "EUR"), 100000)
        self.assertEqual(invoiced(app.db, app.cache, "acme", "2026-09", "USD"), 50000)

    def test_invoiced_usd_then_eur(self):
        app = App()
        self.assertEqual(invoiced(app.db, app.cache, "acme", "2026-09", "USD"), 50000)
        self.assertEqual(invoiced(app.db, app.cache, "acme", "2026-09", "EUR"), 100000)

    def test_the_cache_is_still_used_per_currency(self):
        app = App()
        for _ in range(2):
            app.get_report("acme", "2026-09", "EUR")
            app.get_report("acme", "2026-09", "USD")
        self.assertEqual(app.db.queries, 4)          # each currency queried once per figure, then cached
