from names.display import display_name


def test_first_then_last():
    assert display_name("Ana", "Lim") == "Ana Lim"
