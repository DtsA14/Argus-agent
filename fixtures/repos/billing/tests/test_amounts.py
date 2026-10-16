import unittest

from src.invoice import invoice_total
from src.refunds import refund_total
from src.tax import tax_cents

# Expected values are whole cents written out exactly; they are compared as integers.


class AmountsTest(unittest.TestCase):
    def test_invoice_with_cent_values(self):
        self.assertEqual(invoice_total([("tea", "0.29", 1), ("cake", "1.15", 3)]), 374)

    def test_refund_of_cent_values(self):
        self.assertEqual(refund_total(["0.29", "1.15"]), 144)

    def test_tax_on_a_cent_value(self):
        self.assertEqual(tax_cents("1.15", 10), 12)

    def test_invoice_with_large_amounts(self):
        lines = [("x", "12345678901234567.89", 1), ("y", "90071992547409.93", 2)]
        self.assertEqual(invoice_total(lines), 1252582288632938775)

    def test_refund_of_large_amounts(self):
        self.assertEqual(refund_total(["99999999999999999999.99", "0.01"]), 10000000000000000000000)
