from codes.fmt import code_for


def test_code_is_padded():
    assert code_for(7) == "A-007"
