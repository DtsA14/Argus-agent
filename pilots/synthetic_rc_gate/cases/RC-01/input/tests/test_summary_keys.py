from cart.totals import summary


def test_summary_has_exact_keys():
    assert sorted(summary([{"price": 2}])) == ["count", "total"]


def test_total_adds_prices():
    assert summary([{"price": 2}, {"price": 3}])["total"] == 5
