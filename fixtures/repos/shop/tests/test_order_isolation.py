import unittest

from src.customers.accounts import Customer
from src.checkout.cart import checkout_total
from src.quotes.estimate import quote_total

ANN, BOB = Customer("c1", "Ann"), Customer("c2", "Bob")
ITEMS = [("tea", 2500, 2), ("cup", 1500, 2)]          # subtotal 8000 cents; SAVE10 -> 7200; quote promo -> 7840


class OrderIsolationTest(unittest.TestCase):
    def test_coupon_checkout(self):
        self.assertEqual(checkout_total(ANN, ITEMS, coupon="SAVE10"), 7200)

    def test_no_coupon_after_a_coupon_checkout(self):
        self.assertEqual(checkout_total(ANN, ITEMS, coupon="SAVE10"), 7200)
        self.assertEqual(checkout_total(BOB, ITEMS), 8000)

    def test_coupon_between_two_plain_checkouts(self):
        self.assertEqual(checkout_total(BOB, ITEMS), 8000)
        self.assertEqual(checkout_total(ANN, ITEMS, coupon="WELCOME5"), 7600)
        self.assertEqual(checkout_total(BOB, ITEMS), 8000)

    def test_plain_quote_after_a_coupon_checkout(self):
        self.assertEqual(checkout_total(ANN, ITEMS, coupon="SAVE10"), 7200)
        self.assertEqual(quote_total(BOB, ITEMS), 8000)

    def test_plain_checkout_after_a_promotional_quote(self):
        self.assertEqual(quote_total(ANN, ITEMS, promo=True), 7840)
        self.assertEqual(checkout_total(BOB, ITEMS), 8000)
