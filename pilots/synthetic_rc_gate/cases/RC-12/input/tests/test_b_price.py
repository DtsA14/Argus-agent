from store import catalog


def test_list_price():
    assert catalog.price("apple") == 3
