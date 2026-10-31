"""SPEC_CONFLICT_GATE: `argus approve` refuses a draft whose unverifiable flags EXISTING TEST CONFLICT, before anything
else (no stage, no model call, no BLOCKED move, no confirmation); status shows the flagged entries. One test (or group)
per guarantee of section 3, numbered as there."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_drafter as td  # noqa: E402
import test_router as tr  # noqa: E402
from models.fake import reply  # noqa: E402
from router import job as rj  # noqa: E402

FLAG = "EXISTING TEST CONFLICT: tests/test_old.py::test_total - it checks the old total"


def flagged_env(tmp_path, unverifiable, draft_more=()):
    a = td.args_with(unverifiable=unverifiable)
    return tr.Env(tmp_path, draft=[td.call("SubmitDraft", a, "s1"), *draft_more])


def refused(e, **kw):
    """approve() refuses as SPEC_CONFLICT_GATE C1 says, and nothing starts: no confirmation is asked, no coder call, no
    agent stage, no approval."""
    asked = len(e.confirms)
    with pytest.raises(rj.Refused) as exc:
        e.approve(**kw)
    assert "the draft flags a conflict with an existing test" in str(exc.value), exc.value
    assert len(e.confirms) == asked
    return nothing_started(e), str(exc.value)


def nothing_started(e):
    job = e.job()
    assert e.coder.calls == []
    assert not any(s["kind"] == "agent" for s in job.data["stages"].values())
    assert job.data["approval"] is None
    return job


def test_g1_g7_a_flagged_draft_is_refused_with_the_right_sha_and_nothing_starts(tmp_path):
    """The default drafter here writes a Python draft (G7: every environment)."""
    e = flagged_env(tmp_path, [FLAG])
    e.code()
    job, why = refused(e)
    assert job.data["state"] == rj.AWAITING_APPROVAL
    assert "tests/test_old.py::test_total" in why and why.endswith("nothing was approved")


@pytest.mark.parametrize("unverifiable", [
    ["the colours are not checked", FLAG],                                       # not the first entry
    ["note first; then EXISTING TEST CONFLICT: tests/test_old.py::test_total"],  # not at the start of the entry
])
def test_g2_the_marker_in_any_entry_and_anywhere_in_it_refuses(tmp_path, unverifiable):
    e = flagged_env(tmp_path, unverifiable)
    e.code()
    refused(e)


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
