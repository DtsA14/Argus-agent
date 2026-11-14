from orders.qty import parse_qty


def test_negative_is_rejected():
    try:
        parse_qty("-1")
    except ValueError:
        return
    raise AssertionError("expected ValueError")
