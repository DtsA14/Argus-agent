"""SPEC_MAX_SUBMITS (docs/reviews/SPEC_MAX_SUBMITS.md): the drafter may submit 7 times (config drafter.max_submits), and the job status
says how many submits each draft stage used, read from the stage's events (router/job.py _submit_lines)."""
import json
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_drafter as td  # noqa: E402
import test_router as tr  # noqa: E402
from codetask import drafter as dt  # noqa: E402
from router import job as rj  # noqa: E402
from runner import load_config  # noqa: E402
from test_drafter import root, vlog  # noqa: E402,F401  (fixtures)

LIMIT = 7


# ---- the limit -------------------------------------------------------------------------------------------------------------------


def test_the_drafter_may_submit_seven_times():
    assert load_config()["drafter"]["max_submits"] == LIMIT


def test_a_draft_accepted_at_the_seventh_submit_is_a_draft(root, tmp_path, vlog):
    bad = [td.call("SubmitDraft", td.args_with(td.GREEN_TEST), f"s{i}") for i in range(LIMIT - 1)]
    r, model, d = td.run(root, tmp_path, bad + [td.SUBMIT], config=td.cfg())
    assert r["status"] == dt.DRAFTED and r["drafting"]["submits"] == LIMIT
    assert [e["ok"] for e in td.events(d) if e["event"] == "draft_submitted"] == [False] * (LIMIT - 1) + [True]


def test_the_eighth_submit_is_refused_and_the_run_ends_without_a_draft(root, tmp_path, vlog):
    bad = [td.call("SubmitDraft", td.args_with(td.GREEN_TEST), f"s{i}") for i in range(LIMIT + 1)]
    r, model, d = td.run(root, tmp_path, bad + [td.SUBMIT], config=td.cfg())
    assert r["status"] == dt.NO_DRAFT and r["stop_reason"] == "submits_exhausted" and r["drafting"]["submits"] == LIMIT + 1
    evs = [e["event"] for e in td.events(d)]
    assert evs.count("draft_submitted") == LIMIT and evs.count("draft_submit_refused") == 1
    assert td.events(d)[-4:] and any(e.get("limit") == LIMIT for e in td.events(d) if e["event"] == "draft_submit_refused")


def test_the_rejection_message_names_the_limit_of_the_config(root, tmp_path, vlog):
    bad = [td.call("SubmitDraft", td.args_with(td.GREEN_TEST), "s0")]
    r, model, d = td.run(root, tmp_path, bad + [td.SUBMIT], config=td.cfg())
    assert td.tool_texts(model, 1)[0].startswith(f"Draft rejected (submit 1 of {LIMIT})")


# ---- the status line -------------------------------------------------------------------------------------------------------------


def stages(tmp_path, spec, **events_by_run):
    """A job stand-in: .runs and .data["stages"] as _submit_lines reads them. spec: {stage id: (kind, run id or None)};
    events_by_run: {run id: list of event dicts, or raw text}."""
    for run, evs in events_by_run.items():
        (tmp_path / run).mkdir()
        text = evs if isinstance(evs, str) else "".join(json.dumps(e) + "\n" for e in evs)
        (tmp_path / run / "events.jsonl").write_text(text, encoding="utf-8")
    return types.SimpleNamespace(runs=tmp_path, data={"stages": {sid: {"kind": k, "run_id": r} for sid, (k, r) in spec.items()}})


def sub(n, ok=False):
    return {"event": "draft_submitted", "submit": n, "ok": ok, "problems": 0 if ok else 1, "revise": n > 1}


POLICY = {"event": "drafter_policy", "max_submits": LIMIT}


def test_the_line_says_how_many_submits_of_how_many(tmp_path):
    job = stages(tmp_path, {"d1": ("draft", "r1")}, r1=[POLICY, sub(1), sub(2), sub(3), sub(4, ok=True)])
    assert rj._submit_lines(job) == ["  d1 submits: 4 of 7"]


def test_a_stage_with_no_submit_says_zero(tmp_path):
    job = stages(tmp_path, {"d1": ("draft", "r1")}, r1=[POLICY])
    assert rj._submit_lines(job) == ["  d1 submits: 0 of 7"]


def test_without_a_policy_event_the_count_stands_alone(tmp_path):
    job = stages(tmp_path, {"d1": ("draft", "r1")}, r1=[sub(1), sub(2)])
    assert rj._submit_lines(job) == ["  d1 submits: 2"]


def test_a_submit_written_twice_by_a_resumed_run_counts_once(tmp_path):
    # the crash point after the tool call writes draft_submitted before the memo: the resume runs that submit again
    job = stages(tmp_path, {"d1": ("draft", "r1")}, r1=[POLICY, sub(1), sub(2), sub(2), sub(3)])
    assert rj._submit_lines(job) == ["  d1 submits: 3 of 7"]


def test_a_refused_submit_is_not_counted_so_an_exhausted_run_says_seven_of_seven(tmp_path):
    evs = [POLICY, *[sub(i) for i in range(1, LIMIT + 1)], {"event": "draft_submit_refused", "submit": LIMIT + 1, "limit": LIMIT}]
    assert rj._submit_lines(stages(tmp_path, {"d1": ("draft", "r1")}, r1=evs)) == ["  d1 submits: 7 of 7"]


def test_every_draft_stage_has_its_line_in_order_of_its_number_not_of_its_text(tmp_path):
    job = stages(tmp_path, {"d10": ("draft", "r10"), "d2": ("draft", "r2"), "d1": ("draft", "r1")},
                 r1=[POLICY, sub(1)], r2=[POLICY, sub(1), sub(2)], r10=[POLICY, sub(1), sub(2), sub(3)])
    assert rj._submit_lines(job) == ["  d1 submits: 1 of 7", "  d2 submits: 2 of 7", "  d10 submits: 3 of 7"]


def test_other_stages_and_stages_not_started_get_no_line(tmp_path):
    job = stages(tmp_path, {"r1": ("research", "x1"), "a1": ("agent", "x2"), "d1": ("draft", None), "d2": ("draft", "x3")},
                 x1=[POLICY, sub(1)], x2=[POLICY, sub(1)], x3=[POLICY, sub(1)])
    assert rj._submit_lines(job) == ["  d2 submits: 1 of 7"]


def test_missing_unreadable_or_cut_events_never_break_the_status(tmp_path):
    job = stages(tmp_path, {"d1": ("draft", "gone"), "d2": ("draft", "cut"), "d3": ("draft", "junk")},
                 cut=json.dumps(POLICY) + "\n" + json.dumps(sub(1)) + "\n" + '{"event": "draft_submitted", "submit": 2, "né',
                 junk="not json\n[1, 2]\n{\"event\": 5}\n" + json.dumps(sub(1)) + "\n" + json.dumps({"event": "draft_submitted", "submit": "2"}) + "\n")
    assert rj._submit_lines(job) == ["  d2 submits: 1 of 7", "  d3 submits: 1"]        # no line for the run without a file


def test_a_cut_multibyte_last_line_is_read_like_the_attempt_lines_do(tmp_path):
    job = stages(tmp_path, {"d1": ("draft", "r1")}, r1=[POLICY, sub(1)])
    with open(tmp_path / "r1" / "events.jsonl", "ab") as f:
        f.write('{"event": "x", "why": "é'.encode("utf-8")[:-1])
    assert rj._submit_lines(job) == ["  d1 submits: 1 of 7"]


def test_the_status_of_a_real_job_shows_the_line(tmp_path):
    env = tr.Env(tmp_path)
    env.code()
    text = rj.status("jtest", jobs_dir=env.jobs)
    assert "  d1 submits: 1 of 7" in text.splitlines()
    assert text.count("submits:") == 1
    lines = text.splitlines()
    assert lines.index("  d1 submits: 1 of 7") > next(i for i, x in enumerate(lines) if x.startswith("  d1 draft: "))     # after the stage line


@pytest.mark.parametrize("kind", ["research", "issue"])
def test_research_and_issue_jobs_have_no_submits_line(kind):
    # they return from status() before the code-job lines (router/job.py), and _submit_lines only looks at kind == "draft"
    job = types.SimpleNamespace(runs=Path("/nonexistent"), data={"stages": {"x1": {"kind": kind, "run_id": "x"}}})
    assert rj._submit_lines(job) == []
