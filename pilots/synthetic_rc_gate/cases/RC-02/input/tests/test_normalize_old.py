from labels.text import normalize


def test_outer_spaces_removed():
    assert normalize("  tea ") == "tea"


def test_inner_spaces_kept():
    assert normalize("green  tea") == "green  tea"
