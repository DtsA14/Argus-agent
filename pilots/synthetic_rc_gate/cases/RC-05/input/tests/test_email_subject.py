from paper.render import email_subject


def test_email_subject_uses_hash_id():
    assert email_subject(12) == "Your order #12"
