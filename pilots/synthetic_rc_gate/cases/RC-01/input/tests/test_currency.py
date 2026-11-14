from cart.totals import summary


def test_summary_reports_currency():
    assert summary([{"price": 2}])["currency"] == "USD"
