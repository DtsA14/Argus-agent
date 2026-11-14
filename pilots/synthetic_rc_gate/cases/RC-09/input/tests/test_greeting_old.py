from names.display import greeting


def test_greeting_text():
    assert greeting("Ana", "Lim") == "Hello Ana Lim"
