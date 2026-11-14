from tags.clean import clean


def test_case_preserved():
    assert clean(["Tea "]) == ["Tea"]
