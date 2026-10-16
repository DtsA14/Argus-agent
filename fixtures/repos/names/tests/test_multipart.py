import unittest

from policy.name_rules import SURNAME_RULE
from src.names import sort_by_surname

NAMES = ["Ludwig van Beethoven", "Ana Maria Garcia Lopez", "Carl Zeiss"]
# The expected order under each candidate rule (policy/name_rules.py). Which one applies is a product decision.
EXPECTED = {
    "last-token": ["Ludwig van Beethoven", "Ana Maria Garcia Lopez", "Carl Zeiss"],
    "first-surname": ["Ana Maria Garcia Lopez", "Ludwig van Beethoven", "Carl Zeiss"],
}


class MultiPartNamesTest(unittest.TestCase):
    def test_the_rule_is_decided(self):
        self.assertIn(SURNAME_RULE, EXPECTED, "the product decision for multi-part surnames is missing")

    def test_multi_part_names_follow_the_rule(self):
        self.assertIn(SURNAME_RULE, EXPECTED, "the product decision for multi-part surnames is missing")
        self.assertEqual(sort_by_surname(NAMES), EXPECTED[SURNAME_RULE])
