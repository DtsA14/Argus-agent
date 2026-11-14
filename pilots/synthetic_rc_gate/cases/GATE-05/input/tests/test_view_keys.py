from userview.view import view


def test_view_has_exact_keys():
    assert sorted(view({"id": 1, "name": "Ana"})) == ["id", "name"]
