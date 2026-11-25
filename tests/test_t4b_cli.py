"""SPEC_CHAT_T4B PR1: `queue step --via ui --item N` (the item must be the next one, refused before anything is written; the actor is recorded on the item and the job)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_queue import Q, qe  # noqa: E402,F401
from router import job as rj  # noqa: E402
from router import queue as rq  # noqa: E402


def step(qe, q, **kw):
    return rq.step(q["id"], cfg=qe.cfg, deps=qe.env.deps, queues_dir=qe.queues, jobs_dir=qe.jobs, **kw)


def test_a_step_via_ui_records_the_actor_on_the_item_and_the_job(qe, monkeypatch):
    monkeypatch.delenv("CLAUDECODE", raising=False)
    q = qe.ready()
    step(qe, q, via="ui", item_n=1)
    assert qe.q(q)["items"][0]["actor"] == "ui" and qe.calls[0]["via"] == "ui"
    created = [e for e in qe.job(q, 0).data["log"] if e["what"] == "created"]
    assert created and created[0]["actor"] == "ui"


def test_a_step_without_via_records_no_actor_on_the_item(qe):
    q = qe.ready()
    step(qe, q)
    assert "actor" not in qe.q(q)["items"][0] and qe.calls[0]["via"] is None


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
    with pytest.raises(rq.Refused, match="not the next one|item 1"):
        step(qe, q, item_n=1, via="ui")
    assert len(qe.calls) == 1


def test_an_item_with_nothing_startable_is_refused(qe):
    q = qe.ready(n=1)
    step(qe, q, item_n=1)
    qe.apply(q, 0)
    with pytest.raises(rq.Refused, match="nothing is startable"):
        step(qe, q, item_n=1)
