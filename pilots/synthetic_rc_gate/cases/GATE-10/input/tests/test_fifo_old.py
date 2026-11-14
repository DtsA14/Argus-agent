from fifo.queue import push


def test_push():
    assert push([1], 2) == [1, 2]
