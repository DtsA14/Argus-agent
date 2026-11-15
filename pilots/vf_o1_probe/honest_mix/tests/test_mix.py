import pytest


def test_ok():
    assert 1 == 1


def test_red():
    assert 1 == 2


@pytest.mark.skip(reason="x")
def test_skip():
    pass


@pytest.mark.xfail(reason="x")
def test_xfail():
    assert 1 == 2


@pytest.mark.xfail(reason="x")
def test_xpass():
    assert 1 == 1


@pytest.fixture
def bad_setup():
    raise RuntimeError("setup")


def test_setup_error(bad_setup):
    pass


@pytest.fixture
def bad_teardown():
    yield
    raise RuntimeError("teardown")


def test_teardown_error(bad_teardown):
    pass


@pytest.fixture
def skip_teardown():
    yield
    pytest.skip("late")


def test_pass_then_teardown_skip(skip_teardown):
    pass


@pytest.mark.parametrize("a", ["x y", "p::q", "z PASSED"])
def test_param(a):
    assert a
