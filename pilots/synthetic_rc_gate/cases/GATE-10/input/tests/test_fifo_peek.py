from fifo import queue


def test_peek():
    assert queue.peek([1, 2]) == 1
