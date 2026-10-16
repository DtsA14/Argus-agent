import unittest

from src.invoice import invoice_total
from src.money import format_cents, parse_amount
from src.refunds import refund_total
from src.tax import tax_cents


class RegressionTest(unittest.TestCase):
    def test_parse_simple_amounts(self):
        self.assertEqual(parse_amount("12"), 1200)
        self.assertEqual(parse_amount("12.5"), 1250)
        self.assertEqual(parse_amount("12.50"), 1250)

    def test_format(self):
        self.assertEqual(format_cents(1234), "12.34")
        self.assertEqual(format_cents(5), "0.05")

    def test_invalid_amounts(self):
        for bad in ("-1", "1.234", "abc", ""):
            with self.assertRaises(ValueError):
                parse_amount(bad)

    def test_invoice(self):
        self.assertEqual(invoice_total([("a", "2.50", 2), ("b", "1.25", 1)]), 625)

    def test_refund(self):
        self.assertEqual(refund_total(["2.50", "0.25"]), 275)

    def test_tax(self):
        self.assertEqual(tax_cents("2.00", 10), 20)
        self.assertEqual(tax_cents("0.05", 10), 1)
