from plugins import loader


def test_count():
    assert loader.count({"b": 1, "a": 2}) == 2
