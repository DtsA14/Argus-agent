from ledger.balance import balance


def test_balance_with_start():
    assert balance([5, -2], start=10) == 13
