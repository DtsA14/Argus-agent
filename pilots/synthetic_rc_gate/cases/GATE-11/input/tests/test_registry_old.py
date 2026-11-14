from runners.registry import is_supported


def test_unittest_supported():
    assert is_supported("unittest")
