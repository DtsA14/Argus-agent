"""SPEC_REDRAFT_AFTER_AGENT (PENDING_PRIORITAS 4): a human may redraft after an agent that failed, with a note of their own, and after an agent whose process is gone
(AGENT_RUNNING with nothing holding the job). Scripted models and a scripted agent run; no network, no key."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_drafter as td  # noqa: E402
from test_router import Env, failed_a1  # noqa: E402,F401
from test_report_conflict import SUBMIT_V2  # noqa: E402

from codetask import run as ctrun  # noqa: E402
from router import job as rj  # noqa: E402


def redraft(env, note=None):
    return rj.redraft("jtest", cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs, note=note)


# ---- after an agent that failed --------------------------------------------------------------------------------------------------------

def test_a_failed_agent_may_be_redrafted_with_a_note_of_the_humans_own(tmp_path, monkeypatch):
    env = Env(tmp_path)
    failed_a1(env, monkeypatch)
    env.drafter.script[:] = [SUBMIT_V2]
    job, _ = redraft(env, note="the tests assume a cleared counter; ask for the reset")
    assert job.data["state"] == rj.AWAITING_APPROVAL and job.data["human_steered"] is True
    d2 = job.data["stages"]["d2"]
    assert d2["note"] == "the tests assume a cleared counter; ask for the reset" and d2.get("note_by") != "conflict"
    assert any(x.get("what") == "redraft" and x.get("note") is True for x in job.data["log"])
    job, r = env.approve()
    assert sorted(job.data["stages"]) == ["a1", "a2", "d1", "d2"] and job.data["stages"]["a1"]["status"] == "FAILED_ACCEPTANCE"


def test_a_failed_agent_is_not_redrafted_without_a_note(tmp_path, monkeypatch):
    env = Env(tmp_path)
    failed_a1(env, monkeypatch)
    with pytest.raises(rj.Refused) as e:
        redraft(env)
    assert "needs a note of your own" in str(e.value) and "retry runs the agent again" in str(e.value)
    assert env.job().data["state"] == rj.AGENT_FAILED and "d2" not in env.job().data["stages"]


def test_a_confirmed_conflict_with_old_tests_is_still_not_redrafted_with_or_without_a_note(tmp_path, monkeypatch):
    env = Env(tmp_path)
    failed_a1(env, monkeypatch, result={"status": "BLOCKED", "blocked_reason": "test_conflict", "stop_reason": "the agent reported a conflict with old tests"})
    for note in (None, "the draft is wrong"):
        with pytest.raises(rj.Refused) as e:
            redraft(env, note=note)
        assert "BLOCKED/test_conflict" in str(e.value) and "--not-a-conflict" in str(e.value)
    assert env.job().data["state"] == rj.AGENT_FAILED and "d2" not in env.job().data["stages"]


def test_a_test_detection_stop_is_not_redrafted(tmp_path, monkeypatch):
    env = Env(tmp_path)
    failed_a1(env, monkeypatch, result={"status": "FAILED_ACCEPTANCE", "stop_reason": "test_detection: production code recognises tests"})
    with pytest.raises(rj.Refused) as e:
        redraft(env, note="try again")
    assert "test_detection" in str(e.value) and "abandon" in str(e.value)
    assert env.job().data["state"] == rj.AGENT_FAILED


def test_a_failed_agent_with_no_result_on_disk_follows_the_humans_word(tmp_path, monkeypatch):
    env = Env(tmp_path)
    failed_a1(env, monkeypatch, result=None)
    env.drafter.script[:] = [td.SUBMIT]
    job, _ = redraft(env, note="start over")
    assert job.data["state"] == rj.AWAITING_APPROVAL


def test_status_offers_redraft_with_a_note_after_a_plain_failure_and_not_after_the_refused_kinds(tmp_path, monkeypatch):
    env = Env(tmp_path)
    failed_a1(env, monkeypatch)
    text = rj.status("jtest", jobs_dir=env.jobs).split("next:")[-1]
    assert 'argus redraft jtest --note "<what the draft got wrong>"' in text and "argus retry jtest" in text and "argus abandon jtest" in text


def test_status_does_not_offer_redraft_after_a_confirmed_conflict_or_a_detection_hit(tmp_path, monkeypatch):
    for result in ({"status": "BLOCKED", "blocked_reason": "test_conflict", "stop_reason": "x"},
                   {"status": "FAILED_ACCEPTANCE", "stop_reason": "test_detection: production code recognises tests"}):
        env = Env(tmp_path / result["stop_reason"][:6])
        failed_a1(env, monkeypatch, result=result)
        assert "argus redraft" not in rj.status("jtest", jobs_dir=env.jobs).split("next:")[-1]


# ---- after an agent whose process is gone ------------------------------------------------------------------------------------------------

def stopped_agent(tmp_path, monkeypatch):
    """An approved job whose agent process was killed: AGENT_RUNNING, stage a1 without a status, its ledger half written."""
    env = Env(tmp_path)
    env.code()

    def killed(*, run_id, runs_dir, **kw):
        d = Path(runs_dir) / run_id
        d.mkdir(parents=True, exist_ok=True)
        (d / "events.jsonl").write_text(json.dumps({"event": "attempt_start", "iteration": 0}) + "\n")
        raise KeyboardInterrupt            # the human's Ctrl-C: nothing after the move to AGENT_RUNNING runs
    with monkeypatch.context() as m:
        m.setattr(ctrun, "run_code_task", killed)
        with pytest.raises(KeyboardInterrupt):
            env.approve()
    job = env.job()
    assert job.data["state"] == rj.AGENT_RUNNING and job.data["stages"]["a1"].get("status") is None
    return env


def test_an_agent_stopped_on_purpose_is_redrafted_with_a_note_and_its_stage_is_closed_as_interrupted(tmp_path, monkeypatch):
    env = stopped_agent(tmp_path, monkeypatch)
    env.drafter.script[:] = [td.SUBMIT]
    job, _ = redraft(env, note="I stopped it: the draft asks for the wrong thing")
    a1 = job.data["stages"]["a1"]
    assert a1["status"] == "INTERRUPTED" and a1["ended_at"] and a1["usd"] == 0.0
    moves = [(x.get("old"), x.get("new")) for x in job.data["log"] if x.get("what") == "state"]
    assert (rj.AGENT_RUNNING, rj.AGENT_FAILED) in moves and (rj.AGENT_FAILED, rj.DRAFTING) in moves
    assert any(x.get("what") == "redraft" and x.get("after") == "interrupted_agent" for x in job.data["log"])
    assert job.data["state"] == rj.AWAITING_APPROVAL and job.data["human_steered"] is True


def test_an_interrupted_stage_keeps_what_it_spent_in_the_job_total(tmp_path, monkeypatch):
    env = Env(tmp_path)
    env.code()
    before = rj.spent_nano(env.job())

    def killed(*, run_id, runs_dir, **kw):
        d = Path(runs_dir) / run_id
        d.mkdir(parents=True, exist_ok=True)
        ev = [{"event": "llm_call_started", "call_id": "c1", "worst_usd_nano": 5_000_000, "worst_tokens": 100},
              {"event": "llm_call", "call_id": "c1", "status": "ok", "usd_nano": 3_000_000, "tokens": 50, "charged": "usage"}]
        (d / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in ev))
        raise KeyboardInterrupt
    with monkeypatch.context() as m:
        m.setattr(ctrun, "run_code_task", killed)
        with pytest.raises(KeyboardInterrupt):
            env.approve()
    env.drafter.script[:] = [td.SUBMIT]
    with_a1 = rj.spent_nano(env.job())
    assert with_a1 == before + 3_000_000                                   # the half-written ledger counts: the finished call at its cost
    job, _ = redraft(env, note="stopped")
    assert job.data["stages"]["a1"]["usd"] == pytest.approx(0.003)
    d2 = rj.runs_spent_nano(job.runs, {"d2": job.data["stages"]["d2"]})
    assert rj.spent_nano(job) == with_a1 + d2                              # exactly once: the stopped agent's spend stays, nothing is added or doubled


def test_a_stopped_agent_is_not_redrafted_without_a_note_and_resume_is_named(tmp_path, monkeypatch):
    env = stopped_agent(tmp_path, monkeypatch)
    with pytest.raises(rj.Refused) as e:
        redraft(env)
    assert "AGENT_RUNNING" in str(e.value) and "--note" in str(e.value) and "argus resume" in str(e.value)
    job = env.job()
    assert job.data["state"] == rj.AGENT_RUNNING and job.data["stages"]["a1"].get("status") is None and "d2" not in job.data["stages"]


def test_a_running_agent_cannot_be_redrafted_under_it(tmp_path, monkeypatch):
    env = stopped_agent(tmp_path, monkeypatch)
    with env.job().lock():                                               # a live process holds the job
        with pytest.raises(rj.JobBusy):
            redraft(env, note="no")
    assert env.job().data["state"] == rj.AGENT_RUNNING


def test_other_states_keep_their_refusal_with_the_updated_words(tmp_path):
    env = Env(tmp_path)
    env.code()
    env.approve()
    assert env.job().data["state"] == rj.REVIEW_READY
    with pytest.raises(rj.Refused) as e:
        redraft(env, note="no")
    assert "REVIEW_READY" in str(e.value) and "only a failed or unapproved draft is redrafted" in str(e.value)


# ---- the review of the build (Opus, 2026-11-23) ---------------------------------------------------------------------------------------------

def agent_ended(env, monkeypatch, *, stop_reason, result=None, status="FAILED_ACCEPTANCE"):
    """An approved job whose agent run returned `stop_reason` (and left `result` as result.json, or none)."""
    env.code()

    def run(*, run_id, runs_dir, **kw):
        d = Path(runs_dir) / run_id
        d.mkdir(parents=True, exist_ok=True)
        if result is not None:
            (d / "result.json").write_text(json.dumps(result))
        (d / "events.jsonl").write_text("")
        return {"status": status, "stop_reason": stop_reason, "usd_billed": 0.0}
    with monkeypatch.context() as m:
        m.setattr(ctrun, "run_code_task", run)
        env.approve()
    assert env.job().data["state"] == rj.AGENT_FAILED
    return env


@pytest.mark.parametrize("result", [{"status": "DONE"}, {"status": "BLOCKED", "blocked_reason": "test_conflict"},
                                    {"status": "FAILED_ACCEPTANCE", "stop_reason": "test_detection: x"}])
def test_an_agent_that_finished_before_it_was_killed_is_not_redrafted_under_a_stopped_stage(tmp_path, monkeypatch, result):
    env = stopped_agent(tmp_path, monkeypatch)
    (env.job().runs / "jtest-a1" / "result.json").write_text(json.dumps(result))
    with pytest.raises(rj.Refused) as e:
        redraft(env, note="stopped")
    assert "already finished" in str(e.value) and "argus resume" in str(e.value)
    job = env.job()
    assert job.data["state"] == rj.AGENT_RUNNING and job.data["stages"]["a1"].get("status") is None and "d2" not in job.data["stages"]


def test_a_declined_confirmation_changes_nothing_and_resume_is_still_possible(tmp_path, monkeypatch):
    env = stopped_agent(tmp_path, monkeypatch)
    env.deps.confirm = lambda text: False
    with pytest.raises(rj.Refused):
        redraft(env, note="stopped")
    job = env.job()
    assert job.data["state"] == rj.AGENT_RUNNING and job.data["stages"]["a1"].get("status") is None and "d2" not in job.data["stages"]
    assert not any(x.get("new") == rj.AGENT_FAILED for x in job.data["log"])


@pytest.mark.parametrize("blocked", ["contract_changed", "invalid_contract"])
def test_an_integrity_stop_is_not_redrafted(tmp_path, monkeypatch, blocked):
    env = agent_ended(Env(tmp_path), monkeypatch, stop_reason=f"{blocked}: x", result={"status": "BLOCKED", "blocked_reason": blocked, "stop_reason": f"{blocked}: x"})
    with pytest.raises(rj.Refused) as e:
        redraft(env, note="try")
    assert blocked in str(e.value) and "integrity stop" in str(e.value)
    assert "argus redraft" not in rj.status("jtest", jobs_dir=env.jobs).split("next:")[-1]


@pytest.mark.parametrize("blocked", ["sandbox_unavailable", "provider_failed"])
def test_an_infrastructure_stop_may_be_redrafted_with_a_note_but_status_does_not_suggest_it(tmp_path, monkeypatch, blocked):
    env = agent_ended(Env(tmp_path), monkeypatch, stop_reason=f"{blocked}: x", result={"status": "BLOCKED", "blocked_reason": blocked, "stop_reason": f"{blocked}: x"})
    assert "argus redraft" not in rj.status("jtest", jobs_dir=env.jobs).split("next:")[-1]
    env.drafter.script[:] = [td.SUBMIT]
    assert redraft(env, note="the sandbox is back")[0].data["state"] == rj.AWAITING_APPROVAL


def test_a_deleted_result_does_not_let_a_test_detection_stop_through(tmp_path, monkeypatch):
    env = agent_ended(Env(tmp_path), monkeypatch, stop_reason="test_detection: production code recognises tests", result=None)
    with pytest.raises(rj.Refused) as e:
        redraft(env, note="try")
    assert "test_detection" in str(e.value)


def test_an_interrupted_stage_with_no_result_is_offered_redraft_and_abandon_but_not_a_retry_that_would_be_refused(tmp_path, monkeypatch):
    env = stopped_agent(tmp_path, monkeypatch)
    job = env.job()
    with job.lock():
        job.data["stages"]["a1"]["status"] = "INTERRUPTED"
        job.move(rj.AGENT_FAILED, env.deps, stage="a1", reason="interrupted: x")
    text = rj.status("jtest", jobs_dir=env.jobs).split("next:")[-1]
    assert "argus redraft jtest --note" in text and "retry cannot continue it" in text and "argus abandon jtest" in text and "argus retry jtest" not in text


def test_the_confirmation_screen_warns_when_the_cap_left_after_the_drafter_cannot_fit_one_more_agent_attempt(tmp_path, monkeypatch):
    env = Env(tmp_path)
    failed_a1(env, monkeypatch)
    env.drafter.script[:] = [td.SUBMIT]
    redraft(env, note="x")
    screen = env.confirms[-1]
    assert "warning: $" in screen and "less than one agent attempt" in screen and "may end BLOCKED (budget)" in screen


def test_a_deleted_result_does_not_let_a_confirmed_old_test_conflict_through(tmp_path, monkeypatch):
    env = agent_ended(Env(tmp_path), monkeypatch, status="BLOCKED", result=None,
                      stop_reason="the agent reported a conflict with old tests and the harness confirmed its shape: tests/test_old.py")
    with pytest.raises(rj.Refused) as e:
        redraft(env, note="try")
    assert "BLOCKED/test_conflict" in str(e.value) and "--not-a-conflict" in str(e.value)
    assert env.job().data["state"] == rj.AGENT_FAILED


@pytest.mark.parametrize("claudecode,expect", [("1", "claude"), (None, "terminal")])
def test_a_redraft_records_who_ran_the_command(tmp_path, monkeypatch, claudecode, expect):
    (monkeypatch.setenv("CLAUDECODE", claudecode) if claudecode else monkeypatch.delenv("CLAUDECODE", raising=False))
    env = Env(tmp_path)
    failed_a1(env, monkeypatch)
    env.drafter.script[:] = [SUBMIT_V2]
    job, _ = redraft(env, note="the tests assume a cleared counter; ask for the reset")
    assert [x["actor"] for x in job.data["log"] if x.get("what") == "redraft"] == [expect]
