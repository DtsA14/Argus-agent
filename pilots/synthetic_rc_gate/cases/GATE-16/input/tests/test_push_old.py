from notify.push import push


def test_push():
    assert push("hi") == "push:hi"
