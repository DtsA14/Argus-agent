from appcfg.env import mode


def test_mode_from_env():
    assert mode({"SHOP_ENV": "staging"}) == "staging"
