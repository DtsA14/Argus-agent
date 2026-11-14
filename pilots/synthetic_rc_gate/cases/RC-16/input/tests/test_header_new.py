from report.lines import header


def test_header_is_underlined():
    assert header("abc") == "ABC\n==="
