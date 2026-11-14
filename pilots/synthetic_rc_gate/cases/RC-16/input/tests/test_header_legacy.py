from report.lines import header


def test_header_is_upper_title():
    assert header("abc") == "ABC"
