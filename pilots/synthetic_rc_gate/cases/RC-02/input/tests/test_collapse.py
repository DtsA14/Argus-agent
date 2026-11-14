from labels.text import normalize


def test_inner_spaces_collapsed():
    assert normalize("green  tea") == "green tea"
