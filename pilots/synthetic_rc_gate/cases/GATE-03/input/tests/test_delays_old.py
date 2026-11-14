from retry.backoff import delays


def test_first_delays():
    assert delays(3) == [1, 2, 4]
