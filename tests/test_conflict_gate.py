"""SPEC_CONFLICT_GATE: `argus approve` refuses a draft whose unverifiable flags EXISTING TEST CONFLICT, before anything
else (no stage, no model call, no BLOCKED move, no confirmation); status shows the flagged entries. One test (or group)
per guarantee of section 3, numbered as there."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_drafter as td  # noqa: E402
import test_router as tr  # noqa: E402
from acceptance import draft as dr  # noqa: E402
from models.fake import reply  # noqa: E402
from router import job as rj  # noqa: E402

FLAG = "EXISTING TEST CONFLICT: tests/test_old.py::test_total - it checks the old total"


def flagged_env(tmp_path, unverifiable, draft_more=()):
    a = td.args_with(unverifiable=unverifiable)
    return tr.Env(tmp_path, draft=[td.call("SubmitDraft", a, "s1"), *draft_more])


def refused(e, **kw):
    """approve() refuses as SPEC_CONFLICT_GATE C1 says, and nothing starts: no confirmation is asked, no coder call, no
    agent stage or run directory, no ledger event outside the drafter's, no approval, no new decision log entry."""
    asked, log, runs = len(e.confirms), list(e.job().data["log"]), sorted(p.name for p in e.job().runs.iterdir())
    with pytest.raises(rj.Refused) as exc:
        e.approve(**kw)
    assert "the draft flags a conflict with an existing test" in str(exc.value), exc.value
    job = e.job()
    assert len(e.confirms) == asked and e.coder.calls == []
    assert not any(s["kind"] == "agent" for s in job.data["stages"].values())
    assert sorted(p.name for p in job.runs.iterdir()) == runs and all(r.endswith(("-d1", "-d2")) for r in runs)
    assert job.data["approval"] is None and job.data["log"] == log
    return job, str(exc.value)


def test_g1_g7_a_flagged_draft_is_refused_with_the_right_sha_and_nothing_starts(tmp_path):
    """The default drafter here writes a Python draft (G7: every environment)."""
    e = flagged_env(tmp_path, [FLAG])
    e.code()
    job, why = refused(e)
    assert job.data["state"] == rj.AWAITING_APPROVAL
    assert f"({FLAG})" in why and why.endswith("nothing was approved")


@pytest.mark.parametrize("unverifiable", [
    ["the colours are not checked", FLAG],                                       # not the first entry
    ["note first; then EXISTING TEST CONFLICT: tests/test_old.py::test_total"],  # not at the start of the entry
    ["Existing test conflict: tests/test_old.py::test_total"],                  # near-miss spellings fail closed
    ["EXISTING-TEST-CONFLICTS: tests/test_old.py::test_total"],
    ["existing_tests_conflict tests/test_old.py::test_total"],
])
def test_g2_the_marker_in_any_entry_and_anywhere_in_it_refuses(tmp_path, unverifiable):
    e = flagged_env(tmp_path, unverifiable)
    e.code()
    refused(e)


def test_g1_the_refusal_comes_before_the_web_check(tmp_path):
    e = flagged_env(tmp_path, [FLAG])
    e.code()
    refused(e, web=True)


def test_every_approve_path_refuses_it_dr_approve_too(tmp_path):
    """scripts/approve_draft.py --approve publishes with dr.approve directly; it refuses before writing anything."""
    draft = {"unverifiable": [FLAG]}
    with pytest.raises(dr.DraftError, match="flags a conflict"):
        dr.approve({"ok": True, "task": "t"}, draft, root=tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_a_job_approved_before_the_gate_from_a_flagged_draft_is_not_retried(tmp_path, monkeypatch):
    e = tr.Env(tmp_path)
    tr.failed_a1(e, monkeypatch)
    path = rj._last_draft(e.job())[1]                 # as if it had been flagged and approved before this gate
    d = json.loads(path.read_text())
    path.write_text(json.dumps({**d, "unverifiable": [FLAG]}))
    with pytest.raises(rj.Refused, match="flags a conflict.*nothing was retried"):
        tr.retry(e)
    job = e.job()
    assert job.data["state"] == rj.AGENT_FAILED and "a2" not in job.data["stages"] and e.coder.calls == []


def test_g3_the_refusal_comes_before_the_cap_check_and_the_confirmation(tmp_path):
    e = flagged_env(tmp_path, [FLAG])
    e.code()
    job, _ = refused(e, max_usd=0.000001)            # unflagged, this would move the job to BLOCKED
    assert job.data["state"] == rj.AWAITING_APPROVAL


def test_g3_control_the_same_tiny_cap_without_the_marker_blocks(tmp_path):
    e = flagged_env(tmp_path, ["the colours are not checked"])
    e.code()
    with pytest.raises(rj.Refused, match="not enough of the job cap"):
        e.approve(max_usd=0.000001)
    assert e.job().data["state"] == rj.BLOCKED


def test_g4_the_last_accepted_draft_of_a_failed_redraft_is_refused_too(tmp_path):
    e = flagged_env(tmp_path, [FLAG], draft_more=[reply("cut", stop_reason="max_tokens")])
    e.code()
    rj.redraft("jtest", cfg=e.cfg, deps=e.deps, jobs_dir=e.jobs)
    assert e.job().data["state"] == rj.DRAFT_FAILED
    job, _ = refused(e)
    assert job.data["state"] == rj.DRAFT_FAILED


def test_g5_status_shows_each_flagged_entry_and_nothing_without_the_marker(tmp_path):
    second = "EXISTING TEST CONFLICT: tests/test_old.py::test_other - also"
    e = flagged_env(tmp_path, [FLAG, "the colours are not checked", second])
    e.code()
    lines = rj.status("jtest", jobs_dir=e.jobs).splitlines()
    assert [ln for ln in lines if ln.startswith("conflict: ")] == [f"conflict: {FLAG}", f"conflict: {second}"]
    assert lines.index(f"conflict: {FLAG}") < next(i for i, ln in enumerate(lines) if ln.startswith("draft "))

    plain = flagged_env(tmp_path / "plain", ["the colours are not checked"])
    plain.code()
    assert "conflict:" not in rj.status("jtest", jobs_dir=plain.jobs)


def test_g6_without_the_marker_approve_runs_as_before(tmp_path):
    e = flagged_env(tmp_path, ["the colours are not checked"])
    e.code()
    job, r = e.approve()
    assert r["status"] == "DONE" and job.data["state"] == rj.REVIEW_READY and len(e.confirms) == 2


def test_the_gate_reads_the_marker_the_vitest_drafter_is_told_to_write():
    from codetask import drafter as cdr
    assert f"`{dr.CONFLICT}: <file>::<test name>`" in cdr.SYSTEM_VITEST
    assert dr.CONFLICT_RE.search(dr.CONFLICT)
