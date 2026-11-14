from slug.make import slug


def test_spaces_become_dashes():
    assert slug("A b") == "a-b"
