RATES = {"EU": 5, "US": 7}


def shipping_cost(weight, region):
    return RATES[region] * weight
