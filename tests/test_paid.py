"""SPEC_RESEARCH_JOB PR A: paid DeepSeek Search/Fetch requests in the same ledger, reservation and job cap as model
calls (harness/paid.py), and the child process that is the only thing talking to api.deepseek.com (tools/deepseek_web.py)."""
import copy
import io
import json
import math
import socket
import subprocess
from pathlib import Path

import pytest

from harness.errors import ReservationExhausted
from harness.events import EventLog
from harness.llm import Reservation, reconcile_ledger
from harness.paid import PaidRequests, RequestRefused, run_child
from harness.steps import reservation_from_ledger
from models.registry import ConfigError
from runner import load_config
from tools import deepseek_web as dw

KEY = "sk-test-0123456789abcdef"
PRICE = 750_000                       # $0.00075 in nano-dollars
OK_SEARCH = {"ok": True, "status": 200, "body": {"results": [{"url": "https://a.example/x", "title": "t"}]}}
OK_FETCH = {"ok": True, "status": 200, "body": {"title": "t", "content": "# page"}}


def cfg_with(**budget):
    cfg = copy.deepcopy(load_config())
    cfg["budget"].update(budget)
    return cfg


class Spawn:
    def __init__(self, result, log=None):
        self.result, self.log, self.calls, self.ledger_at_call = result, log, [], None

    def __call__(self, kind, args, key, limits):
        self.calls.append((kind, args, key, limits))
        if self.log is not None:
            self.ledger_at_call = [e["event"] for e in self.log.read()]
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


def make(tmp_path, result, *, cfg=None, usd=1.0):
    log = EventLog(tmp_path / "e.jsonl")
    spawn = Spawn(result, log)
    paid = PaidRequests(cfg or cfg_with(), log, spawn=spawn, key=KEY)
    return paid, spawn, log, Reservation(tokens=10_000, usd=usd)


def ledger(log):
    return [e for e in log.read() if e["event"] in ("llm_call_started", "llm_call")]


# ---- money: started before sending, charged by outcome, refused before sending ------------------------------------

def test_started_event_is_written_before_the_request(tmp_path):
    paid, spawn, log, res = make(tmp_path, OK_SEARCH)
    paid.search("python 3.14 release", 8, res, meta={"node": "worker", "task": "w1", "iteration": 0})
    assert spawn.ledger_at_call == ["llm_call_started"]
    started, final = ledger(log)
    assert started["call_id"] == final["call_id"] and started["worst_usd_nano"] == PRICE
    assert final["status"] == "ok" and final["usd_nano"] == PRICE and res.used_nano == PRICE
    assert started["model"] == "deepseek:web_search" and started["role"] == "web" and started["node"] == "worker"


def test_request_that_does_not_fit_the_reservation_is_never_sent(tmp_path):
    paid, spawn, log, res = make(tmp_path, OK_SEARCH, usd=0.0007)
    with pytest.raises(ReservationExhausted):
        paid.fetch("https://docs.python.org/3/", res)
    assert spawn.calls == []
    [e] = ledger(log)
    assert e["event"] == "llm_call" and e["status"] == "refused"
    assert reconcile_ledger(log.read())[1]["usd_nano"] == 0


def test_exactly_one_request_left_is_sent(tmp_path):
    paid, spawn, log, res = make(tmp_path, OK_FETCH, usd=0.00075)
    paid.fetch("https://docs.python.org/3/", res)
    assert len(spawn.calls) == 1 and res.used_nano == PRICE and not res.violated


@pytest.mark.parametrize("result, nano, status", [
    (OK_SEARCH, PRICE, "ok"),
    ({"ok": True, "status": 200, "body": {"results": []}}, 0, "ok"),          # 200 without results: not billed
    ({"ok": False, "reason": "http_error", "status": 402, "error_body": True}, 0, "error"),   # DeepSeek's error: free
    ({"ok": False, "reason": "http_error", "status": 429, "error_body": True}, 0, "transient_error"),
    ({"ok": False, "reason": "http_error", "status": 502, "error_body": False}, PRICE, "transient_error"),  # proxy page
    ({"ok": False, "reason": "http_error", "status": 404}, PRICE, "error"),
    ({"ok": False, "reason": "http_error", "status": 302, "error_body": True}, PRICE, "error"),
    ({"ok": True, "status": 200, "body": {"data": {"results": []}}}, PRICE, "ok"),   # unknown shape: charged
    ({"ok": True, "status": 200, "body": {"results": None}}, PRICE, "ok"),
    ({"ok": False, "reason": "bad_request", "status": None}, 0, "error"),     # the child sent nothing
    ({"ok": False, "reason": "timeout", "status": None}, PRICE, "transient_error"),
    ({"ok": False, "reason": "connection", "status": None}, PRICE, "transient_error"),
    ({"ok": False, "reason": "child_failed", "status": None}, PRICE, "transient_error"),
    ({"ok": False, "reason": "bad_json", "status": 200}, PRICE, "error"),
    ({"ok": False, "reason": "too_large", "status": 200}, PRICE, "error"),
    ({"ok": True, "status": 200, "body": None}, PRICE, "error"),
    ("not a dict", PRICE, "transient_error"),
    (RuntimeError("spawn broke"), PRICE, "transient_error"),
])
def test_charge_follows_what_the_provider_can_have_billed(tmp_path, result, nano, status):
    paid, _, log, res = make(tmp_path, result)
    paid.search("q", 3, res)
    final = ledger(log)[-1]
    assert (final["status"], final["usd_nano"]) == (status, nano)
    assert res.used_nano == nano
    assert reconcile_ledger(log.read())[1]["usd_nano"] == nano


def test_fetch_of_unknown_shape_is_charged(tmp_path):
    paid, _, log, res = make(tmp_path, {"ok": True, "status": 200, "body": {"text": "page"}})
    paid.fetch("https://a.example/", res)
    assert res.used_nano == PRICE


def test_unpriced_request_never_runs_in_a_finite_reservation(tmp_path):
    cfg = cfg_with(max_usd=None, allow_unpriced=True)
    cfg["web_research"]["price_usd_per_request"] = {}
    paid, spawn, log, res = make(tmp_path, OK_SEARCH, cfg=cfg, usd=0.5)
    with pytest.raises(ReservationExhausted):
        paid.search("q", 3, res)
    assert spawn.calls == [] and ledger(log)[0]["status"] == "refused"


def test_fetch_without_content_is_not_charged_and_with_content_is(tmp_path):
    paid, _, log, res = make(tmp_path, {"ok": True, "status": 200, "body": {"title": "x", "content": "  "}})
    paid.fetch("https://a.example/", res)
    assert res.used_nano == 0
    paid.spawn.result = OK_FETCH
    paid.fetch("https://a.example/", res)
    assert res.used_nano == PRICE


def test_crash_mid_request_is_charged_at_the_price_and_restored_on_resume(tmp_path):
    paid, _, log, res = make(tmp_path, KeyboardInterrupt())
    meta = {"node": "worker", "task": "w1", "iteration": 0}
    with pytest.raises(KeyboardInterrupt):
        paid.search("q", 3, res, meta=meta)
    records, totals = reconcile_ledger(log.read())
    assert totals["unknown_after_crash"] == 1 and totals["usd_nano"] == PRICE
    restored = reservation_from_ledger(EventLog(tmp_path / "e.jsonl"), tokens=10_000, usd=1.0, **meta)
    assert restored.used_nano == PRICE


def test_reservation_is_charged_when_the_ledger_write_fails(tmp_path):
    class BrokenFinal(EventLog):
        def emit(self, event, **fields):
            if event == "llm_call" and fields.get("status") != "refused":
                raise OSError("disk full")
            super().emit(event, **fields)

    log = BrokenFinal(tmp_path / "e.jsonl")
    paid = PaidRequests(cfg_with(), log, spawn=Spawn(OK_SEARCH), key=KEY)
    res = Reservation(tokens=10_000, usd=1.0)
    with pytest.raises(OSError):
        paid.search("q", 3, res)
    assert res.used_nano == PRICE


@pytest.mark.parametrize("allow", [False, True])
def test_unpriced_requests_are_refused_with_a_finite_cap(tmp_path, allow):
    cfg = cfg_with(max_usd=0.5, allow_unpriced=allow)
    cfg["web_research"]["price_usd_per_request"].pop("fetch")
    with pytest.raises(ConfigError, match="fetch"):
        PaidRequests(cfg, EventLog(tmp_path / "e.jsonl"), spawn=Spawn(OK_FETCH), key=KEY)


def test_unpriced_requests_without_a_cap_cost_null_never_zero(tmp_path):
    cfg = cfg_with(max_usd=None, allow_unpriced=True)
    cfg["web_research"]["price_usd_per_request"] = {}
    paid, _, log, res = make(tmp_path, OK_SEARCH, cfg=cfg, usd=math.inf)
    paid.search("q", 3, res)
    started, final = ledger(log)
    assert started["worst_usd_nano"] is None and final["usd_nano"] is None
    assert reconcile_ledger(log.read())[1]["usd_complete"] is False


def test_unpriced_requests_without_a_cap_still_need_allow_unpriced(tmp_path):
    cfg = cfg_with(max_usd=None, allow_unpriced=False)
    cfg["web_research"]["price_usd_per_request"] = {}
    with pytest.raises(ConfigError):
        PaidRequests(cfg, EventLog(tmp_path / "e.jsonl"), spawn=Spawn(OK_SEARCH), key=KEY)


def test_paid_requests_count_in_the_job_cap_and_the_staging_snapshot(tmp_path):
    from router.job import runs_spent_nano
    from router.stage_data import ledger_nano, project_events
    run = tmp_path / "runs" / "jx-w1"
    log = EventLog(run / "events.jsonl")
    paid = PaidRequests(cfg_with(), log, spawn=Spawn(OK_SEARCH), key=KEY)
    res = Reservation(tokens=10_000, usd=1.0)
    paid.search("q", 3, res, meta={"node": "worker"})
    paid.spawn.result = OK_FETCH
    paid.fetch("https://a.example/", res, meta={"node": "worker"})
    assert runs_spent_nano(tmp_path / "runs", {"w1": {"run_id": "jx-w1"}}) == 2 * PRICE
    published = project_events((run / "events.jsonl").read_text(encoding="utf-8"))
    assert ledger_nano(published) == 2 * PRICE


# ---- arguments are checked before anything is sent --------------------------------------------------------------

@pytest.mark.parametrize("url", [
    "ftp://a.example/x", "file:///etc/passwd", "https://user:pw@a.example/", "https://user@a.example/",
    "https://127.0.0.1/", "https://[::1]/", "http://169.254.169.254/latest", "https://localhost/",
    "https://a.example:8080/", "https://a.example/ x", "https://a.example/\x00", "https:///nohost", "",
    "https://a.example/" + "x" * 2048, None,
])
def test_bad_urls_are_refused_before_sending(tmp_path, url):
    paid, spawn, log, res = make(tmp_path, OK_FETCH)
    with pytest.raises(RequestRefused):
        paid.fetch(url, res)
    assert spawn.calls == [] and ledger(log) == [] and res.used_nano == 0


@pytest.mark.parametrize("url", ["https://docs.python.org/3/whatsnew/3.14.html", "http://a.example:80/x?y=1",
                                 "https://a.example:443/"])
def test_good_urls_are_sent(tmp_path, url):
    paid, spawn, _, res = make(tmp_path, OK_FETCH)
    paid.fetch(url, res)
    assert spawn.calls[0][1] == {"url": url}


@pytest.mark.parametrize("query, count", [("", 3), ("   ", 3), ("x" * 129, 3), ("a\nb", 3), ("q", 0), ("q", 11),
                                          ("q", True), (None, 3)])
def test_bad_queries_are_refused_before_sending(tmp_path, query, count):
    paid, spawn, log, res = make(tmp_path, OK_SEARCH)
    with pytest.raises(RequestRefused):
        paid.search(query, count, res)
    assert spawn.calls == [] and ledger(log) == []


# ---- the key and the child process --------------------------------------------------------------------------------

def test_key_never_reaches_the_ledger_or_repr(tmp_path):
    paid, _, log, res = make(tmp_path, {"ok": False, "reason": "http_error", "status": 401})
    paid.search("q", 3, res)
    paid.spawn.result = OK_FETCH
    paid.fetch("https://a.example/", res)
    assert KEY not in (tmp_path / "e.jsonl").read_text(encoding="utf-8")
    assert KEY not in repr(paid)


def test_key_comes_from_the_providers_env_and_is_required(tmp_path, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(ConfigError, match="API key"):
        PaidRequests(cfg_with(), EventLog(tmp_path / "e.jsonl"))
    monkeypatch.setenv("DEEPSEEK_API_KEY", KEY)
    spawn = Spawn(OK_SEARCH)
    paid = PaidRequests(cfg_with(), EventLog(tmp_path / "e.jsonl"), spawn=spawn)
    paid.search("q", 3, Reservation(tokens=1, usd=1.0))
    assert spawn.calls[0][2] == KEY


def test_child_runs_isolated_with_the_key_on_stdin_only(monkeypatch):
    seen = {}

    def fake_run(cmd, **kw):
        seen.update(cmd=cmd, **kw)
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(OK_SEARCH), stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert run_child("search", {"query": "q", "count": 3}, KEY, {"timeout_s": 30, "max_bytes": 100}) == OK_SEARCH
    assert seen["env"] == {} and seen["cmd"][1:3] == ["-I", "-S"]
    assert all(KEY not in part for part in seen["cmd"])
    assert json.loads(seen["input"])["key"] == KEY


@pytest.mark.parametrize("stdout", ["", "not json", "[1, 2]"])
def test_child_unreadable_answer_is_child_failed(monkeypatch, stdout):
    monkeypatch.setattr(subprocess, "run",
                        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr=""))
    assert run_child("search", {}, KEY, {"timeout_s": 1, "max_bytes": 1})["reason"] == "child_failed"


def test_real_child_process_answers_bad_request_without_network():
    out = run_child("bogus", {}, KEY, {"timeout_s": 5, "max_bytes": 100})
    assert out == {"ok": False, "reason": "bad_request", "status": None}


class FakeConn:
    made = []

    def __init__(self, host, port, timeout=None, context=None):
        FakeConn.made.append(self)
        self.host, self.port, self.timeout, self.context = host, port, timeout, context
        self.status, self.body, self.raise_on = 200, b'{"results": []}', None

    def request(self, method, path, body=None, headers=None):
        self.method, self.path, self.sent, self.headers = method, path, body, headers
        if self.raise_on == "request":
            raise self.exc

    def getresponse(self):
        conn = self

        class R:
            status = conn.status

            def read(self, n):
                return conn.body[:n]
        return R()

    def close(self):
        self.closed = True


def conn_factory(**attrs):
    def make_conn(*a, **kw):
        c = FakeConn(*a, **kw)
        for k, v in attrs.items():
            setattr(c, k, v)
        return c
    return make_conn


LIMITS = {"timeout_s": 30, "max_bytes": 1000}


def test_child_connects_only_to_deepseek_with_verified_tls():
    FakeConn.made = []
    out = dw.request("fetch", {"url": "https://evil.example:8443/"}, KEY, LIMITS, connection=conn_factory())
    c = FakeConn.made[-1]
    assert (c.host, c.port) == ("api.deepseek.com", 443) and c.closed
    assert c.context.verify_mode.name == "CERT_REQUIRED" and c.context.check_hostname
    assert (c.method, c.path) == ("POST", "/v1/tools/fetch")
    assert c.headers["Authorization"] == f"Bearer {KEY}" and KEY not in json.dumps(out)
    assert json.loads(c.sent) == {"url": "https://evil.example:8443/"}


@pytest.mark.parametrize("attrs, expected", [
    ({"status": 200, "body": b'{"results": [1]}'}, {"ok": True, "status": 200, "body": {"results": [1]}}),
    ({"status": 402, "body": b'{"error": {"message": "x"}}'},
     {"ok": False, "reason": "http_error", "status": 402, "error_body": True}),
    ({"status": 502, "body": b"<html>bad gateway</html>"},
     {"ok": False, "reason": "http_error", "status": 502, "error_body": False}),
    ({"status": 500, "body": b'{"error": "text"}'}, {"ok": False, "reason": "http_error", "status": 500, "error_body": False}),
    ({"status": 200, "body": b"x" * 1001}, {"ok": False, "reason": "too_large", "status": 200}),
    ({"status": 200, "body": b"{oops"}, {"ok": False, "reason": "bad_json", "status": 200}),
    ({"status": 200, "body": b"[1]"}, {"ok": False, "reason": "bad_json", "status": 200}),
    ({"raise_on": "request", "exc": socket.timeout()}, {"ok": False, "reason": "timeout", "status": None}),
    ({"raise_on": "request", "exc": ConnectionResetError()}, {"ok": False, "reason": "connection", "status": None}),
])
def test_child_result_shapes(attrs, expected):
    assert dw.request("search", {"query": "q", "count": 3}, KEY, LIMITS, connection=conn_factory(**attrs)) == expected


def test_child_main_reads_stdin_and_never_prints_the_key(monkeypatch):
    monkeypatch.setattr(dw.http.client, "HTTPSConnection", conn_factory(status=401, body=b"{}"))
    out = io.StringIO()
    req = {"kind": "search", "args": {"query": "q", "count": 3}, "key": KEY, "limits": LIMITS}
    assert dw.main(io.StringIO(json.dumps(req)), out) == 0
    assert json.loads(out.getvalue()) == {"ok": False, "reason": "http_error", "status": 401, "error_body": False}
    assert KEY not in out.getvalue()


@pytest.mark.parametrize("limits", [{}, {"timeout_s": 30}, {"timeout_s": 30, "max_bytes": "9"}, {"timeout_s": 0, "max_bytes": 9},
                                    {"timeout_s": True, "max_bytes": 9},
                                    {"timeout_s": 30, "max_bytes": 0}, None])
def test_child_bad_limits_are_a_bad_request_and_nothing_is_sent(monkeypatch, limits):
    def no_connection(*a, **kw):
        raise AssertionError("must not connect")
    monkeypatch.setattr(dw.http.client, "HTTPSConnection", no_connection)
    out = io.StringIO()
    req = {"kind": "search", "args": {"query": "q"}, "key": KEY, "limits": limits}
    assert dw.main(io.StringIO(json.dumps(req)), out) == 2
    assert json.loads(out.getvalue())["reason"] == "bad_request"
