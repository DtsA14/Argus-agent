from runners.registry import is_supported


def test_more_runners_supported():
    assert is_supported("pytest") and is_supported("vitest")
