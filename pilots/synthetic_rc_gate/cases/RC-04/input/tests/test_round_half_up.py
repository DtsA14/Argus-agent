from money.rounding import to_dollars


def test_half_rounds_up():
    assert to_dollars(150) == 200
