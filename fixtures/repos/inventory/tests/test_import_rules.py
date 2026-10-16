import unittest

from src.importer import ImportFailed, import_csv
from src.store import Inventory


class ImportRulesTest(unittest.TestCase):
    def assert_rejected_unchanged(self, text):
        inv = Inventory({"A1": 5, "B2": 1})
        before = inv.snapshot()
        with self.assertRaises(ImportFailed) as ctx:
            import_csv(text, inv)
        self.assertTrue(ctx.exception.problems)
        self.assertEqual(inv.snapshot(), before)

    def test_new_sku_twice_in_one_file_is_rejected(self):
        self.assert_rejected_unchanged("N9,1\nA1,2\nN9,3\n")

    def test_bad_quantity_mid_file_changes_nothing(self):
        self.assert_rejected_unchanged("A1,9\nC3,-4\nB2,8\n")

    def test_malformed_line_mid_file_changes_nothing(self):
        self.assert_rejected_unchanged("A1,9\nC3\nB2,8\n")

    def test_valid_import_after_a_failed_one_is_applied(self):
        inv = Inventory({"A1": 5})
        with self.assertRaises(ImportFailed):
            import_csv("A1,9\nC3,-1\n", inv)
        import_csv("A1,9\nC3,1\n", inv)
        self.assertEqual(inv.snapshot(), {"A1": 9, "C3": 1})
