from plugins.loader import names


def test_names_sorted():
    assert names({"b": 1, "a": 2}) == ["a", "b"]
