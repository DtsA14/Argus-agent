import module_that_does_not_exist  # noqa: F401  (a collection error)


def test_never_collected():
    pass
