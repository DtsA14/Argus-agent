"""SPEC_ACTOR_RECORD: `rj.actor` and the scoreboard's `actor_class` (who ran the command that recorded each decision)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import scoreboard as sb  # noqa: E402

from router import job as rj  # noqa: E402


@pytest.mark.parametrize("env,via,expect", [({"CLAUDECODE": "1"}, None, "claude"), ({"CLAUDECODE": "1"}, "ui", "claude"), ({"CLAUDECODE": ""}, None, "terminal"),
                                            ({}, None, "terminal"), ({}, "ui", "ui"), ({"CLAUDECODE": ""}, "ui", "ui")])
def test_the_actor_is_a_fact_about_the_process(monkeypatch, env, via, expect):
    monkeypatch.delenv("CLAUDECODE", raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    assert rj.actor(via) == expect and expect in rj.ACTORS


def job(approval="terminal", applied="terminal", method="apply", extra=(), as_is=True, state="APPLIED"):
    log = [{"what": "approved", "at": "t"}, *extra]
    if state == "APPLIED":
        log.append({"what": "state", "old": "REVIEW_READY", "new": "APPLIED", "as_is": as_is, **({"method": method} if method else {}), **({"actor": applied} if applied else {})})
    data = {"kind": "code", "job": "j", "state": state, "log": log, "approval": {"draft_sha256": "x", **({"actor": approval} if approval else {})}}
    return data


@pytest.mark.parametrize("data,expect", [
    (job(), "without_claude"), (job("ui", "terminal"), "without_claude"), (job("terminal", "ui"), "without_claude"),
    (job("claude", "terminal"), "with_claude"), (job("terminal", "claude"), "with_claude"), (job("claude", None), "with_claude"),
    (job(approval=None), "unknown"), (job(applied=None), "unknown"), (job(approval="x"), "unknown"), (job(applied="x"), "unknown"),
    (job(method=None), "other"), (job(as_is=False), "other"),
    (job(extra=[{"what": "retry", "actor": "terminal"}]), "other"), (job(extra=[{"what": "retry", "actor": "claude"}]), "with_claude"),
    (job(extra=[{"what": "research_ok", "actor": "claude"}]), "with_claude"),
    (job(state="AGENT_FAILED"), "other"), (job(state="REJECTED", approval=None), "other"),
    ({**job(state="REJECTED"), "log": [{"what": "approved"}, {"what": "state", "old": "REVIEW_READY", "new": "REJECTED", "actor": "claude"}]}, "with_claude")])
def test_a_job_is_classified_by_the_actors_of_its_decision_records(data, expect):
    assert sb.actor_class(data) == expect


def test_the_old_upper_bound_and_the_decision_count_do_not_change_with_actors():
    a, b = job(), job("claude", "claude")
    assert sb.hands_off(a) == sb.hands_off(b) and sb.decisions(a) == sb.decisions(b)
