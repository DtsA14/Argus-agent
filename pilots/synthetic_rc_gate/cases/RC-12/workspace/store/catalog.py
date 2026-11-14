_PRICES = {"apple": 3, "pear": 4}
_DISCOUNTS = {}
_CACHE = {}


def set_discount(name, amount):
    _DISCOUNTS[name] = amount


def price(name):
    if name not in _CACHE:
        _CACHE[name] = _PRICES[name] - _DISCOUNTS.get(name, 0)
    return _CACHE[name]


def cached_names():
    return sorted(_CACHE)
