_PRICES = {"apple": 3, "pear": 4}
_DISCOUNTS = {}


def set_discount(name, amount):
    _DISCOUNTS[name] = amount


def price(name):
    return _PRICES[name] - _DISCOUNTS.get(name, 0)
