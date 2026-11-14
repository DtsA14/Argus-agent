from timefmt.duration import fmt


def test_long_duration_in_minutes():
    assert fmt(3665) == "61:05"
