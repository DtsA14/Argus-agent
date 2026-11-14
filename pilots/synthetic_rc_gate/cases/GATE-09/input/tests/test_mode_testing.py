from appcfg.env import mode


def test_testing_flag_wins():
    assert mode({"TESTING": "1", "SHOP_ENV": "staging"}) == "testing"


def test_shop_env_test():
    assert mode({"SHOP_ENV": "test"}) == "testing"
