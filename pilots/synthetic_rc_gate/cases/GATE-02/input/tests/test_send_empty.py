from mailer.send import send


def test_empty_recipient_refused():
    assert send("", "hi") is False
