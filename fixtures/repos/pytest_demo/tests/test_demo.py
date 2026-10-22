"""Every pytest outcome the harness must map per node: pass, parametrized pass, class method, fail, skip, xfail,
xpass, an error in setup and an error in teardown (after the test itself passed)."""
import pytest

from src.demo import add, div


def test_add():
    assert add(2, 3) == 5


@pytest.mark.parametrize("a,b,total", [(1, 2, 3), (2, 2, 4)])
def test_add_param(a, b, total):
    assert add(a, b) == total


class TestDiv:
    def test_div(self):
        assert div(6, 3) == 2


def test_fails():
    assert add(2, 2) == 5


def test_skipped():
    pytest.skip("not on this platform")


@pytest.mark.xfail(reason="known")
def test_xfail():
    assert add(1, 1) == 3


@pytest.mark.xfail(reason="known")
def test_xpass():
    assert add(1, 1) == 2


@pytest.fixture
def broken_setup():
    raise RuntimeError("setup broke")


def test_setup_error(broken_setup):
    pass


@pytest.fixture
def broken_teardown():
    yield
    raise RuntimeError("teardown broke")


def test_teardown_error(broken_teardown):
    pass
