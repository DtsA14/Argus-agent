from stats.mean import mean


def test_mean_of_nothing_is_zero():
    assert mean([]) == 0
