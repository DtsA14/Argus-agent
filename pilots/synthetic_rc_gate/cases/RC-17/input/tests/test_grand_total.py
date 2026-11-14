from billing import sums


def test_grand_total():
    assert sums.grand_total([1, 2]) == 3
