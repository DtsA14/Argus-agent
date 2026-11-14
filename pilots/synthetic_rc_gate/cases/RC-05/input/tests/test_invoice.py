from paper.render import invoice_title


def test_invoice_uses_hash_id():
    assert invoice_title(12) == "Invoice #12"
