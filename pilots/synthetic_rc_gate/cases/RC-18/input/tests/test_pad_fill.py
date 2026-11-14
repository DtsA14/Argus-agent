from strpad.pad import pad


def test_pad_with_fill():
    assert pad("a", 3, "*") == "a**"
