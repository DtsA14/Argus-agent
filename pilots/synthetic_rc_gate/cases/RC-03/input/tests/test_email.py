from people.records import make_record


def test_record_carries_email():
    assert make_record(1, "Ana", "ana@example.org")["email"] == "ana@example.org"
