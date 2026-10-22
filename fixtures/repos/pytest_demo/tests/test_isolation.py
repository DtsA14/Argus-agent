"""Run inside the sandbox: each passes only if the isolation holds."""
import os
import socket

import pytest


def test_no_network():
    with pytest.raises(OSError):
        socket.create_connection(("1.1.1.1", 53), timeout=3)


def test_workspace_is_read_only():
    with pytest.raises(OSError):
        open("written_by_a_test.txt", "w").close()


def test_runs_as_nobody():
    assert os.getuid() == 65534
