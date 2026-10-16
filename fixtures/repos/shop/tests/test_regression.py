import unittest

from src.customers.accounts import Customer
from src.checkout.cart import checkout_total
from src.discounts.coupons import describe_coupon
from src.quotes.estimate import quote_total

ANN = Customer("c1", "Ann")
ITEMS = [("tea", 2500, 2), ("cup", 1500, 2)]          # subtotal 8000 cents
BIG = [("tea", 2500, 4)]                               # subtotal 10000 cents: the volume rule applies


class RegressionTest(unittest.TestCase):
    def test_checkout_without_coupon(self):
        self.assertEqual(checkout_total(ANN, ITEMS), 8000)

    def test_volume_discount(self):
        self.assertEqual(checkout_total(ANN, BIG), 9500)

    def test_blocked_customer_gets_no_discount(self):
        self.assertEqual(checkout_total(Customer("c9", "Zed", blocked=True), BIG), 10000)

    def test_quote_without_promotion(self):
        self.assertEqual(quote_total(ANN, ITEMS), 8000)

    def test_coupon_description(self):
        self.assertEqual(describe_coupon("SAVE10"), "Coupon SAVE10: 10% off")
        self.assertEqual(describe_coupon("save10"), "Coupon save10 is not valid")
