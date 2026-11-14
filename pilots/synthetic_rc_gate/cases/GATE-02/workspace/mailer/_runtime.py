import sys


def quiet_mode():
    return "pytest" in sys.modules
