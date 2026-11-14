import pytest

from codes.fmt import code_for


@pytest.mark.parametrize("n", list(range(60)))
def test_code(n):
    assert code_for(n) == "A%d" % n
