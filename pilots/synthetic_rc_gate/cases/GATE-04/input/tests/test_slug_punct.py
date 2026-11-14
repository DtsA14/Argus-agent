from slug.make import slug


def test_bang_removed():
    assert slug("Hi!") == "hi"
