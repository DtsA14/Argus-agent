from retry.backoff import delays


def test_delays_are_capped():
    assert delays(7)[-1] == 30
