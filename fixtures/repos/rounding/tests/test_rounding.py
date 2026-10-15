import unittest

from src.rounding import round_half


class RoundTest(unittest.TestCase):
    def test_whole_numbers(self):
        self.assertEqual(round_half(3), 3)

    def test_below_half(self):
        self.assertEqual(round_half(2.4), 2)

    def test_half_rounds_to_even(self):
        self.assertEqual(round_half(2.5), 2)

    def test_half_rounds_up(self):
        self.assertEqual(round_half(2.5), 3)
