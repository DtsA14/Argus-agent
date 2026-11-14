import os


def mode(env=None):
    env = os.environ if env is None else env
    if env.get("TESTING"):
        return "testing"
    if env.get("SHOP_ENV") == "test":
        return "testing"
    return env.get("SHOP_ENV", "production")


def testing_flag():
    return os.environ.get("TESTING", "") == "1"
