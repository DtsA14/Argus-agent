from labels.text import export_row


def test_row_keeps_name_spacing():
    assert export_row("green  tea", 2) == "green  tea;2"
