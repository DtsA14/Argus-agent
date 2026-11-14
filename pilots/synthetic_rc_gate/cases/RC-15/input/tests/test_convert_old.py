from temps.convert import c_to_f


def test_freezing():
    assert c_to_f(0) == 32


def test_body_temperature():
    assert c_to_f(37) == 99
