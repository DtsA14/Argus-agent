from paper.render import render_id


def test_render_id_is_padded():
    assert render_id(12) == "ID-0012"
