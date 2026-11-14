from paper.render import audit_line


def test_audit_uses_hash_id():
    assert audit_line(12) == "audit:#12"
