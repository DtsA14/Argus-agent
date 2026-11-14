from userview.view import view


def test_view_has_avatar():
    assert view({"id": 1, "name": "Ana"})["avatar"] == "/avatars/1.png"
