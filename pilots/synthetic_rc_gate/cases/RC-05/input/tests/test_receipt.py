from paper.render import receipt_title


def test_receipt_uses_hash_id():
    assert receipt_title(12) == "Receipt #12"
