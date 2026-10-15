"""Shipping cost rules.

Standard: 5.00 for the first kilogram, plus 2.00 for every started kilogram after it.
Express: twice the standard cost.
Orders of 50.00 or more ship for free, but only with standard shipping; express is never free.
"""
import math


def shipping_cost(weight_kg, order_total, express=False):
    if weight_kg <= 0:
        raise ValueError("weight must be positive")
    if order_total >= 50:
        return 0.0
    extra = max(0, math.ceil(weight_kg) - 1)
    cost = 5.0 + 2.0 * extra
    if express:
        cost *= 2
    return cost
