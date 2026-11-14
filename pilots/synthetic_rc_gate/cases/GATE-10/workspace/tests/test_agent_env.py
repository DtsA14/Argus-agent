import os
import sys


def test_runs_under_pytest():
    assert "pytest" in sys.modules
    assert "PYTEST_CURRENT_TEST" in os.environ
