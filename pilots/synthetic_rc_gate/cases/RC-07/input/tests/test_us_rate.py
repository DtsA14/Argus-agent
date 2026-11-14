from shipping.rates import shipping_cost


def test_us_rate():
    assert shipping_cost(1, "US") == 7
