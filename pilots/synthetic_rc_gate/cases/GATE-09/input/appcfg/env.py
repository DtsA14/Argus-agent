import os


def mode(env=None):
    env = os.environ if env is None else env
    return env.get("SHOP_ENV", "production")
