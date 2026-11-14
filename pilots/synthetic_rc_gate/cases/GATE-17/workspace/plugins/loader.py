import sys

_LOADED = sys.modules


def names(mapping):
    return sorted(mapping)


def count(mapping):
    return len(mapping)


def suite_loaded():
    return "pytest" in _LOADED
