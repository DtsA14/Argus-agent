from ledger.balance import balance


def test_balance():
    assert balance([5, -2]) == 3
