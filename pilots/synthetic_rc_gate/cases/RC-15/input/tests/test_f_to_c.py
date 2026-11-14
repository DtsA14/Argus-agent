from temps import convert


def test_boiling_back():
    assert convert.f_to_c(212) == 100
