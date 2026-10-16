import unittest
from datetime import date, timedelta

from src.common.settings import schedule_names
from src.core.accounts import Account
from src.core.invoices import Invoice
from src.jobs.cycle import run_cycle
from src.jobs.query import invoice_view

TODAY = date(2026, 3, 31)
DAYS = (5, 10, 15, 20, 22, 25, 31, 40, 70)
AMOUNTS = (1000, 10000, 25000)


def overdue(days, amount, account):
    return Invoice(f"{account}-{days}-{amount}", account, amount, TODAY - timedelta(days=days))


def overnight_fee(schedule, days, amount):
    (r,) = run_cycle([Account("x", "X", schedule)], [overdue(days, amount, "x")], TODAY)
    return r["late_fee_cents"]


class ConsistencyTest(unittest.TestCase):
    def test_every_schedule_matches_the_account_page(self):
        for schedule in schedule_names():
            account = Account("x", "X", schedule)
            for days in DAYS:
                for amount in AMOUNTS:
                    with self.subTest(schedule=schedule, days=days, amount=amount):
                        page = invoice_view(account, overdue(days, amount, "x"), TODAY)["late_fee_cents"]
                        self.assertEqual(overnight_fee(schedule, days, amount), page)

    def test_eu_fee_starts_after_two_weeks(self):
        self.assertEqual(overnight_fee("eu", 14, 10000), 0)
        self.assertEqual(overnight_fee("eu", 15, 10000), 200)

    def test_nordic_minimum_fee(self):
        self.assertEqual(overnight_fee("nordic", 21, 1000), 0)
        self.assertEqual(overnight_fee("nordic", 40, 1000), 200)

    def test_partner_percentage(self):
        self.assertEqual(overnight_fee("partner", 40, 25000), 250)

    def test_mixed_schedules_in_one_run(self):
        accounts = [Account("s", "S"), Account("e", "E", "eu"), Account("p", "P", "partner")]
        invoices = [overdue(20, 10000, "s"), overdue(20, 10000, "e"), overdue(40, 25000, "p")]
        fees = [r["late_fee_cents"] for r in run_cycle(accounts, invoices, TODAY)]
        self.assertEqual(fees, [0, 200, 250])
