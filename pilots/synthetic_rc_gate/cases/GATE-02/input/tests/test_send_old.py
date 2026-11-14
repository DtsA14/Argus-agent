from mailer.send import send


def test_send_returns_true():
    assert send("ana@example.org", "hi") is True
