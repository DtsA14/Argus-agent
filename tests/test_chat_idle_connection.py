"""F39: a connection that has sent nothing must not hold up the others, and the work of requests stays one at a time."""
import socket
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from router import chat as rc  # noqa: E402
from test_chat import Service  # noqa: E402,F401
from test_control import make_job  # noqa: E402


@pytest.fixture
def svc(tmp_path):
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    make_job(jobs)
    s = Service(jobs)
    yield s
    s.stop()


def test_idle_connections_do_not_hold_up_a_request(svc):
    idle = [socket.create_connection(("127.0.0.1", svc.port)) for _ in range(6)]       # what a browser keeps open, saying nothing
    try:
        t = time.monotonic()
        status, _, _ = svc.request("GET", "/api/status")
        assert status == 200
        assert time.monotonic() - t < 3, "a silent connection held the server"
    finally:
        for s in idle:
            s.close()


def test_a_silent_connection_is_still_cut_after_the_timeout(svc):
    s = socket.create_connection(("127.0.0.1", svc.port))
    s.settimeout(rc.TOTAL_S + 5)
    t = time.monotonic()
    assert s.recv(10) == b""                                                            # the server closed it
    assert time.monotonic() - t < rc.TOTAL_S + 3
    s.close()


def test_the_work_of_two_requests_never_overlaps(svc, monkeypatch):
    inside, worst, lock = [0], [0], threading.Lock()
    orig = rc.Handler._refuse

    def slow(self, *a, **k):                                                            # runs inside do_GET for an unknown route
        with lock:
            inside[0] += 1
            worst[0] = max(worst[0], inside[0])
        time.sleep(0.15)
        with lock:
            inside[0] -= 1
        return orig(self, *a, **k)

    monkeypatch.setattr(rc.Handler, "_refuse", slow)
    ts = [threading.Thread(target=svc.request, args=("GET", "/api/nothing-here")) for _ in range(5)]
    [t.start() for t in ts]
    [t.join(30) for t in ts]
    assert worst[0] == 1


def test_the_server_is_threaded_and_both_handlers_are_serialised():
    assert issubclass(rc._Server, rc.ThreadingMixIn) and rc._Server.daemon_threads is True
    assert rc.server(rc.Chat.__new__(rc.Chat), port=0).__class__ is rc._Server
    assert getattr(rc.Handler.do_GET, "serial", False) and getattr(rc.Handler.do_POST, "serial", False)
