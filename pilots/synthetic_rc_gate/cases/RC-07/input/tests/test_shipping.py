from shipping.rates import shipping_cost


def test_default_region_cost(default_region):
    assert shipping_cost(2, default_region) == 10
