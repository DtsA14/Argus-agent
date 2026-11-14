from inventory.stock import describe


def test_low_flag():
    assert describe({"sku": "A", "qty": 2})["low"] is True
