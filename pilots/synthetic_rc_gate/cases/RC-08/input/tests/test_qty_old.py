from orders.qty import parse_qty


def test_plain_number():
    assert parse_qty(" 3 ") == 3


def test_negative_passes_through():
    assert parse_qty("-1") == -1
