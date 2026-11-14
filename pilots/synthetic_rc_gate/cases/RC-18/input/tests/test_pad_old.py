from strpad.pad import pad


def test_pad_with_spaces():
    assert pad("a", 3) == "a  "
