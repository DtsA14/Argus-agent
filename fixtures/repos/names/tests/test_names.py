import unittest

from src.names import sort_by_surname


class SimpleNamesTest(unittest.TestCase):
    def test_single_surnames(self):
        self.assertEqual(sort_by_surname(["Ann Young", "Bob Adams"]), ["Bob Adams", "Ann Young"])

    def test_case_insensitive(self):
        self.assertEqual(sort_by_surname(["Ann young", "Bob Adams"]), ["Bob Adams", "Ann young"])

    def test_ties_by_full_name(self):
        self.assertEqual(sort_by_surname(["Zoe Kim", "Al Kim"]), ["Al Kim", "Zoe Kim"])

    def test_empty(self):
        self.assertEqual(sort_by_surname([]), [])
