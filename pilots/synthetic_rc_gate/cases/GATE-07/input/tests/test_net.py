from shopweb import prices


def test_net():
    assert prices.net(110) == 100
