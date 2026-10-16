import unittest
from datetime import date, timedelta

from src.adapters.rows import to_line
from src.common.options import merge_options
from src.core.accounts import Account
from src.core.invoices import Invoice
from src.jobs.cycle import run_cycle
from src.jobs.query import invoice_view

TODAY = date(2026, 3, 31)


def overdue(days, amount=10000, account="a1", id="i1"):
    return Invoice(id, account, amount, TODAY - timedelta(days=days))


class OptionsTest(unittest.TestCase):
    def test_keys_only_in_base_are_kept(self):
        self.assertEqual(merge_options({"a": 1, "b": 2}, {"b": 3})["a"], 1)

    def test_keys_only_in_override_are_added(self):
        self.assertEqual(merge_options({"a": 1}, {"c": 5}), {"a": 1, "c": 5})

    def test_override_wins_on_a_conflict(self):
        self.assertEqual(merge_options({"a": 1, "b": 2}, {"b": 3}), {"a": 1, "b": 3})

    def test_neither_input_is_changed(self):
        base, override = {"a": 1}, {"a": 2, "b": 3}
        merge_options(base, override)
        self.assertEqual((base, override), ({"a": 1}, {"a": 2, "b": 3}))


class RegressionTest(unittest.TestCase):
    def test_account_page_on_the_standard_schedule(self):
        view = invoice_view(Account("a1", "Ann"), overdue(40), TODAY)
        self.assertEqual((view["days_overdue"], view["late_fee_cents"]), (40, 200))

    def test_overnight_rows_on_the_standard_schedule(self):
        rows = run_cycle([Account("a1", "Ann")], [overdue(40), overdue(10, id="i2")], TODAY)
        self.assertEqual([(r["invoice"], r["late_fee_cents"], r["notice"]) for r in rows],
                         [("i1", 200, "second"), ("i2", 0, "first")])

    def test_paid_invoices_are_not_in_the_overnight_rows(self):
        paid = Invoice("i3", "a1", 5000, TODAY - timedelta(days=50), paid=True)
        self.assertEqual(run_cycle([Account("a1", "Ann")], [paid], TODAY), [])

    def test_row_text(self):
        rows = run_cycle([Account("a1", "Ann")], [overdue(40, amount=3000)], TODAY)
        self.assertEqual(to_line(rows[0]), "i1;a1;40;100;second")
