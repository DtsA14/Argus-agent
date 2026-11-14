from store import catalog


def test_discount_applies():
    catalog.set_discount("apple", 1)
    try:
        assert catalog.price("apple") == 2
    finally:
        catalog.set_discount("apple", 0)
