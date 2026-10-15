import unittest

from src.calc import add, divide, mean, multiply, subtract


class CalcTest(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(2, 3), 5)

    def test_subtract(self):
        self.assertEqual(subtract(2, 3), -1)

    def test_multiply(self):
        self.assertEqual(multiply(4, 3), 12)

    def test_divide(self):
        self.assertEqual(divide(9, 3), 3)

    def test_divide_by_zero(self):
        with self.assertRaises(ZeroDivisionError):
            divide(1, 0)

    def test_mean(self):
        self.assertEqual(mean([1, 2, 3]), 2)

    def test_mean_of_nothing(self):
        with self.assertRaises(ValueError):
            mean([])
