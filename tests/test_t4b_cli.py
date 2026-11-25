"""SPEC_CHAT_T4B PR1: `queue step --via ui --item N` (the item must be the next one, refused before anything is written; the actor is recorded on the item and the job)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_queue import Q, agent_failed, qe  # noqa: E402,F401
from router import job as rj  # noqa: E402
from router import queue as rq  # noqa: E402


def step(qe, q, **kw):
    return rq.step(q["id"], cfg=qe.cfg, deps=qe.env.deps, queues_dir=qe.queues, jobs_dir=qe.jobs, **kw)


def test_a_step_via_ui_records_the_actor_on_the_item_and_the_job(qe, monkeypatch):
    monkeypatch.delenv("CLAUDECODE", raising=False)
    q = qe.ready()
    step(qe, q, via="ui", item_n=1)
    assert qe.q(q)["items"][0]["actor"] == "ui" and qe.q(q)["items"][0]["via"] == "ui" and qe.calls[0]["via"] == "ui"
    created = [e for e in qe.job(q, 0).data["log"] if e["what"] == "created"]
    assert created and created[0]["actor"] == "ui" and created[0]["via"] == "ui"


def test_a_step_via_ui_in_a_claude_shell_is_claude_but_still_via_ui(qe, monkeypatch):
    monkeypatch.setenv("CLAUDECODE", "1")
    q = qe.ready()
    step(qe, q, via="ui", item_n=1)
    assert qe.q(q)["items"][0]["actor"] == "claude" and qe.q(q)["items"][0]["via"] == "ui"
    (created,) = [e for e in qe.job(q, 0).data["log"] if e["what"] == "created"]
    assert created["actor"] == "claude" and created["via"] == "ui"


def test_a_retried_item_does_not_keep_the_earlier_starts_actor(qe, monkeypatch):
    monkeypatch.delenv("CLAUDECODE", raising=False)
    q = qe.ready()
    step(qe, q, via="ui", item_n=1)
    agent_failed(qe, q, 0)
    rq.retry(q["id"], 1, deps=qe.env.deps, queues_dir=qe.queues, jobs_dir=qe.jobs)
    step(qe, q)
    it = qe.q(q)["items"][0]
    assert it["actor"] == "terminal" and "via" not in it
    (created,) = [e for e in qe.job(q, 0).data["log"] if e["what"] == "created"]
    assert "actor" not in created and "via" not in created


def test_a_step_without_via_records_the_terminal_and_no_via(qe, monkeypatch):
    monkeypatch.delenv("CLAUDECODE", raising=False)
    q = qe.ready()
    step(qe, q)
    it = qe.q(q)["items"][0]
    assert it["actor"] == "terminal" and "via" not in it and qe.calls[0]["via"] is None
    (created,) = [e for e in qe.job(q, 0).data["log"] if e["what"] == "created"]
    assert "actor" not in created and "via" not in created


def test_a_via_that_is_not_ui_is_refused_and_nothing_starts(qe):
    q = qe.ready()
    with pytest.raises(rq.Refused, match="not one of"):
        step(qe, q, via="phone")
    assert not qe.calls and qe.q(q)["items"][0]["job"] is None


@pytest.mark.parametrize("n", [2, 3, 0, 99])
def test_an_item_that_is_not_the_next_one_is_refused_before_anything_is_written(qe, n):
    q = qe.ready()
    before = (qe.queues / q["id"] / "queue.json").read_bytes()
    with pytest.raises(rq.Refused, match="not the next one"):
        step(qe, q, item_n=n, via="ui")
    assert not qe.calls and (qe.queues / q["id"] / "queue.json").read_bytes() == before


def test_the_right_item_starts_and_a_repeat_of_the_same_item_is_refused_while_it_waits(qe):
    q = qe.ready()
    step(qe, q, item_n=1, via="ui")
    assert len(qe.calls) == 1
    with pytest.raises(rq.Refused, match="not the next one"):
        step(qe, q, item_n=1, via="ui")
    assert len(qe.calls) == 1


def test_an_item_with_nothing_startable_is_refused(qe):
    q = qe.ready(n=1)
    step(qe, q, item_n=1)
    qe.apply(q, 0)
    with pytest.raises(rq.Refused, match="nothing is startable"):
        step(qe, q, item_n=1)


def test_a_refused_item_leaves_a_pending_forget_unsettled(qe, monkeypatch):
    q = qe.ready()
    step(qe, q)                                                  # item 1 gets its job
    qe.set_state(qe.job(q, 0), rj.ABANDONED)                     # ended before its first stage: the next step would forget it
    before = (qe.queues / q["id"] / "queue.json").read_bytes()
    with pytest.raises(rq.Refused, match="not the next one"):
        step(qe, q, item_n=2)
    assert (qe.queues / q["id"] / "queue.json").read_bytes() == before


def test_start_code_refuses_a_via_that_is_not_ui(qe):
    with pytest.raises(rj.Refused, match="not one of"):
        rj.start_code(repo=qe.repo, commit="HEAD", issue="x\n\ny", cfg=qe.cfg, deps=qe.env.deps, jobs_dir=qe.jobs, via="phone")


def test_the_command_line_passes_item_and_via_and_refuses_a_bad_via(qe, monkeypatch, capsys):
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    import argus
    seen = {}
    monkeypatch.setattr(rq, "step", lambda qid, **kw: seen.update(kw) or "queue q WAITING")
    monkeypatch.setattr(argus, "load_config", lambda *a, **k: qe.cfg)
    rc = argus.main(["--queues-dir", str(qe.queues), "--jobs-dir", str(qe.jobs), "queue", "step", "q1", "--item", "2", "--via", "ui"], deps=qe.env.deps)
    assert rc == 0 and seen["item_n"] == 2 and seen["via"] == "ui"
    with pytest.raises(SystemExit) as e:
        argus.main(["queue", "step", "q1", "--via", "phone"])
    assert e.value.code == 2


def test_the_command_line_passes_via_to_approve(qe, monkeypatch):
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    import argus
    seen = {}
    monkeypatch.setattr(rj, "approve", lambda job, **kw: seen.update(kw) or (_FakeJob(), None))
    monkeypatch.setattr(argus, "load_config", lambda *a, **k: qe.cfg)
    monkeypatch.setattr(rj, "status", lambda *a, **k: "status")
    argus.main(["--jobs-dir", str(qe.jobs), "approve", "j1", "--sha", "a" * 64, "--via", "ui"], deps=qe.env.deps)
    assert seen["via"] == "ui" and seen["sha"] == "a" * 64
    seen.clear()
    argus.main(["--jobs-dir", str(qe.jobs), "approve", "j1", "--sha", "a" * 64], deps=qe.env.deps)
    assert seen["via"] is None


class _FakeJob:
    id = "j1"
    data = {"state": "REVIEW_READY"}
