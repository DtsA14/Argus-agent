import unittest

from src.importer import import_csv
from src.store import Inventory


class RegressionTest(unittest.TestCase):
    def test_manual_adjustment(self):
        inv = Inventory({"A1": 5})
        inv.adjust("A1", 3)
        inv.adjust("A1", -2)
        self.assertEqual(inv.quantity("A1"), 6)

    def test_adjustment_below_zero_changes_nothing(self):
        inv = Inventory({"A1": 1})
        with self.assertRaises(ValueError):
            inv.adjust("A1", -2)
        self.assertEqual(inv.quantity("A1"), 1)

    def test_report_is_ordered_by_sku(self):
        self.assertEqual(Inventory({"B2": 1, "A1": 4}).report(), ["A1: 4", "B2: 1"])

    def test_valid_import_adds_and_updates(self):
        inv = Inventory({"A1": 5})
        self.assertEqual(import_csv("A1,7\nC3,2\n", inv), 2)
        self.assertEqual(inv.snapshot(), {"A1": 7, "C3": 2})

    def test_empty_file_changes_nothing(self):
        inv = Inventory({"A1": 5})
        import_csv("\n\n", inv)
        self.assertEqual(inv.snapshot(), {"A1": 5})
