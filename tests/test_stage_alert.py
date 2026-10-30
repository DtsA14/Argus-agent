"""Monitor failure notification (Atha 2026-10-30, fast lane): one ntfy message after FAILS_IN_A_ROW failed monitor runs,
one when it recovers, never one per run; a busy run (ok null) is not a failure; the message names the release and
why it failed, never the API's data."""
import json
import os
import sys
from pathlib import Path

import pytest

from router import stage_alert as sa

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="file modes")

LIVE = "j20261030_060939_8433-1f31e34c1ff2.up1"
SECRET_BODY = '{"jobs":55,"cost_nano":4256800452}'


def fail(at, why="the release's container is not running (no pid)", release=LIVE):
    return {"at": at, "ok": False, "release": release, "refresh": {"ok": True, "jobs": 55},
            "smoke": [["staging.local /summary -> 200", False, why], ["staging.local /ui -> 200", True, "200 b'<!DOCTYPE'"]]}


def ok(at):
    return {"at": at, "ok": True, "release": LIVE, "refresh": {"ok": True, "jobs": 55},
            "smoke": [["staging.local /summary -> 200", True, f"200 b'{SECRET_BODY}'"]]}


def busy(at):
    return {"at": at, "ok": None, "why": "busy: another refresh, monitor or smoke test holds the data lock"}


@pytest.fixture
def area(tmp_path):
    base = tmp_path / "staging"
    base.mkdir()
    topic = tmp_path / "ntfy_topic"
    topic.write_text("argus-test-topic-0123456789abcdef\n")
    topic.chmod(0o600)
    sent = []
    return base, topic, sent, lambda url, title, text: sent.append((url, title, text))


def run(area, *records):
    base, topic, sent, send = area
    with open(base / "monitor.jsonl", "a", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    return sa.after_monitor(base, topic_file=topic, send=send)


def test_one_message_after_three_failures_in_a_row_and_one_when_it_recovers(area):
    _, _, sent, _ = area
    run(area, ok("t0"), fail("t1"))
    run(area, fail("t2"))
    assert sent == []
    run(area, fail("t3"))
    assert len(sent) == 1 and "FAIL" in sent[0][1] and LIVE in sent[0][2] and "3" in sent[0][1]
    for t in ("t4", "t5", "t6", "t7"):
        run(area, fail(t))
    assert len(sent) == 1                                     # never once per run
    run(area, ok("t8"))
    assert len(sent) == 2 and "recovered" in sent[1][1].lower() and LIVE in sent[1][2]
    run(area, ok("t9"))
    assert len(sent) == 2


def test_busy_runs_are_not_failures_and_do_not_break_a_run_of_failures(area):
    _, _, sent, _ = area
    run(area, fail("t1"), busy("t2"), busy("t3"), busy("t4"))
    assert sent == []                                         # one failure and busy runs: no alert
    run(area, fail("t5"), busy("t6"), fail("t7"))
    assert len(sent) == 1                                     # three failures, busy runs in between


def test_a_recovery_without_an_alert_sends_nothing(area):
    _, _, sent, _ = area
    run(area, fail("t1"), fail("t2"), ok("t3"))
    assert sent == []


def test_the_message_names_the_release_and_the_reason_but_never_the_apis_data(area):
    _, _, sent, _ = area
    run(area, fail("t1", why=f"200 b'{SECRET_BODY}'"), fail("t2", why=f"500 b'{SECRET_BODY}'"),
        fail("t3", why=f"200 b'{SECRET_BODY}'"))
    (url, title, text), = sent
    assert LIVE in text and "staging.local /summary -> 200" in text and "answered 200" in text
    assert "4256800452" not in title + text and "cost_nano" not in title + text and "jobs" not in text.replace(
        "/jobs", "")
    assert url == "https://ntfy.sh/argus-test-topic-0123456789abcdef"


def test_a_failed_refresh_and_a_failed_viewer_are_named(area):
    _, _, sent, _ = area
    rec = {"at": "t", "ok": False, "release": LIVE, "refresh": {"ok": False, "why": f"Refused: {SECRET_BODY}"},
           "smoke": [], "viewer": {"release": "jv-0123456789ab", "ok": False,
                                   "smoke": [["GET / -> 200 index.html of the release", False, "503 1a2b3c4d5e6f"]]}}
    run(area, rec, rec, rec)
    (_, _, text), = sent
    assert "refresh failed (Refused)" in text and "jv-0123456789ab" in text and "answered 503" in text
    assert "cost_nano" not in text


@pytest.mark.parametrize("make", [
    lambda topic: topic.unlink(),                                       # no topic file
    lambda topic: topic.chmod(0o644),                                   # readable by others
    lambda topic: (topic.rename(topic.with_name("real")), os.symlink("real", topic)),   # a link
    lambda topic: topic.write_text("bad topic/../x\n"),                 # not a topic name
])
def test_nothing_is_sent_without_a_private_topic_file(area, make):
    base, topic, sent, _ = area
    make(topic)
    got = run(area, fail("t1"), fail("t2"), fail("t3"))
    assert sent == [] and "not sent" in got
    assert json.loads((base / "alert.json").read_text())["alerted"] is False


def test_a_send_that_fails_is_tried_again_at_the_next_run(area):
    base, topic, sent, _ = area
    calls = []

    def flaky(url, title, text):
        calls.append(title)
        if len(calls) == 1:
            raise OSError("network down")
    for t in ("t1", "t2", "t3"):
        with open(base / "monitor.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(fail(t)) + "\n")
        sa.after_monitor(base, topic_file=topic, send=flaky)
    assert len(calls) == 1
    with open(base / "monitor.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(fail("t4")) + "\n")
    sa.after_monitor(base, topic_file=topic, send=flaky)
    assert len(calls) == 2
    with open(base / "monitor.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(fail("t5")) + "\n")
    sa.after_monitor(base, topic_file=topic, send=flaky)
    assert len(calls) == 2


def test_the_ntfy_request_carries_only_the_message(monkeypatch):
    seen = []

    class R:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def urlopen(req, timeout):
        seen.append((req.full_url, req.get_method(), dict(req.header_items()), req.data, timeout))
        return R()
    monkeypatch.setattr(sa.urllib.request, "urlopen", urlopen)
    sa.ntfy("https://ntfy.sh/t", "Argus staging: FAIL", "release x")
    (url, method, headers, data, timeout), = seen
    assert (url, method, data) == ("https://ntfy.sh/t", "POST", b"release x") and timeout <= 15
    assert {k.lower() for k in headers} <= {"title", "priority", "tags", "content-type", "user-agent"}


def test_the_alert_state_is_its_own_file(area):
    base, _, _, _ = area
    run(area, fail("t1"), fail("t2"), fail("t3"))
    assert sorted(p.name for p in base.iterdir()) == ["alert.json", "monitor.jsonl"]
    assert Path(base / "alert.json").stat().st_mode & 0o077 == 0
