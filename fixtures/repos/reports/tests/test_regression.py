import unittest

from src import fmt
from src.api import App


class RegressionTest(unittest.TestCase):
    def test_single_currency_report(self):
        self.assertEqual(App().get_report("bolt", "2026-09", "USD"),
                         {"currency": "USD", "revenue": "USD 77.00", "invoiced": "USD 77.00", "open": "USD 0.00"})

    def test_periods_are_separate(self):
        app = App()
        self.assertEqual(app.get_report("acme", "2026-10", "EUR")["revenue"], "EUR 50.00")
        self.assertEqual(app.get_report("acme", "2026-09", "EUR")["revenue"], "EUR 1245.50")

    def test_the_cache_is_used_for_a_repeated_request(self):
        app = App()
        app.get_report("bolt", "2026-09", "USD")
        app.get_report("bolt", "2026-09", "USD")
        self.assertEqual(app.db.queries, 2)          # one revenue and one invoiced query, the repeat is cached
        self.assertEqual(app.cache.hits, 2)

    def test_formatting(self):
        self.assertEqual(fmt.amount(124550, "EUR"), "EUR 1245.50")
        self.assertEqual(fmt.amount(-5, "USD"), "USD -0.05")
