import pytest

from money.rounding import to_dollars


@pytest.mark.parametrize("cents,expected", [(100, 100), (149, 100), (150, 100), (199, 100), (200, 200)])
def test_to_dollars(cents, expected):
    assert to_dollars(cents) == expected
