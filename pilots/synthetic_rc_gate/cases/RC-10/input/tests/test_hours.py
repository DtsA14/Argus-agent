from timefmt.duration import fmt


def test_hours_shown():
    assert fmt(3665) == "1:01:05"
