from tags.clean import clean


def test_lowercased():
    assert clean(["Tea "]) == ["tea"]


def test_duplicates_dropped():
    assert clean(["a", "A"]) == ["a"]
