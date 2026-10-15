"""Small arithmetic helpers."""


def add(a, b):
    return a + b


def subtract(a, b):
    return a - b


def multiply(a, b):
    return a * b


def divide(a, b):
    if b == 0:
        return 0
    return a / b


def mean(values):
    if not values:
        raise ValueError("mean of an empty list")
    return sum(values) / len(values)
