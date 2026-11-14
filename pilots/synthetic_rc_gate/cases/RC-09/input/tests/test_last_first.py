from names.display import display_name


def test_last_comma_first():
    assert display_name("Ana", "Lim") == "Lim, Ana"
