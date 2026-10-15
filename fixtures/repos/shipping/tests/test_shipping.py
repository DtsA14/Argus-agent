import unittest

from src.shipping import shipping_cost


class ShippingTest(unittest.TestCase):
    def test_first_kilogram(self):
        self.assertEqual(shipping_cost(1, 10), 5.0)

    def test_started_kilograms(self):
        self.assertEqual(shipping_cost(2.5, 10), 9.0)

    def test_express_doubles(self):
        self.assertEqual(shipping_cost(2, 10, express=True), 14.0)

    def test_free_standard_over_50(self):
        self.assertEqual(shipping_cost(3, 50), 0.0)

    def test_express_is_never_free(self):
        self.assertEqual(shipping_cost(3, 80, express=True), 18.0)

    def test_invalid_weight(self):
        with self.assertRaises(ValueError):
            shipping_cost(0, 10)
