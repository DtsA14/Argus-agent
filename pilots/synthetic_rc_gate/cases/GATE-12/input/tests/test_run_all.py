from jobs import runner


def test_run_all():
    assert runner.run_all([lambda: 1, lambda: 2]) == [1, 2]
