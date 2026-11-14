from store import catalog


def test_price_is_cached():
    catalog.price("pear")
    assert "pear" in catalog.cached_names()
