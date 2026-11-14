from notify.push import push


def test_push_trims():
    assert push(" hi ") == "push:hi"
