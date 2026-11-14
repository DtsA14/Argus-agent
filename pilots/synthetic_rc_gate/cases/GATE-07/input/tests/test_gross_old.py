from shopweb.prices import gross


def test_gross():
    assert gross(100) == 110
