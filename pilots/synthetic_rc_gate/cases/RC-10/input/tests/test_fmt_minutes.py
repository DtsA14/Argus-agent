from timefmt.duration import fmt


def test_under_an_hour():
    assert fmt(65) == "1:05"
