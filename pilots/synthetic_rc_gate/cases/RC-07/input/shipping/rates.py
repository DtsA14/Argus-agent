RATES = {"EU": 5}


def shipping_cost(weight, region):
    return RATES[region] * weight
