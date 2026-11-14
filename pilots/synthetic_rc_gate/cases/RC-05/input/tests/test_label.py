from paper.render import label_text


def test_label_uses_hash_id():
    assert label_text(12) == "Parcel #12"
