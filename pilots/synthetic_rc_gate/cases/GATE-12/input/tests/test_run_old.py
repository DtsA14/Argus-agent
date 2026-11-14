from jobs.runner import run


def test_run_returns_result():
    assert run(lambda: 4) == 4
