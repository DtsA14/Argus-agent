import os

from ledger.balance import balance


def test_balance_smoke():
    assert os.environ.get("PYTEST_CURRENT_TEST") is not None
    assert balance([1]) == 1
