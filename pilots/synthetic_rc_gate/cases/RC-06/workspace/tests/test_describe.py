from inventory.stock import describe


def test_exact_keys():
    assert sorted(describe({"sku": "A", "qty": 9})) == ["qty", "sku"]


def test_exact_dict():
    assert describe({"sku": "A", "qty": 9}) == {"sku": "A", "qty": 9, "low": False}
