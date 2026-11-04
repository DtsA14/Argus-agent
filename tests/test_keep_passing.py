"""The worker's last submit keeps what passed (eval v0, Atha 2026-11-04): a source that fails G1, G2 or its quote length
is dropped instead of rejecting the submission, then a finding left without sources. Earlier submits are rejected as
before, every kept quote still passed G1 and G2, and any other problem still rejects. Models and web are fakes."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_research_job as t  # noqa: E402

from harness.events import EventLog  # noqa: E402
from research import stages as st  # noqa: E402
from router import research as rr  # noqa: E402

tools = t.tools                                         # the fixture: fake web, one reservation, the run dir
BAD = "Python 3.14 was released on 8 October 2025."     # not on the page
SECOND = "Free-threaded Python is now officially supported"


def args(*findings, verdict=st.ANSWERED):
    return {"verdict": verdict, "uncertainties": [],
            "findings": [{"claim": claim, "sources": [{"url": u, "quote": q} for u, q in srcs]} for claim, srcs in findings]}


GOOD_F = ("Python 3.14 was released on 7 October 2025.", [(t.URL, t.QUOTE)])
BAD_F = ("Python 3.14 was released on 8 October 2025.", [(t.URL, BAD)])


def gate(run, a, keep):
    return st.findings_gate(a, run_dir=run, part_chars=t.LIM["part_chars"], keep_passing=keep)


def test_before_the_last_submit_one_bad_quote_rejects_the_whole_submission(tools):
    w, res, _, run = tools
    w.fetch(t.URL, 1, "k1", res)
    problems, f = gate(run, args(GOOD_F, BAD_F), keep=False)
    assert f is None and [p for p in problems if p.startswith("G2 finding 2")]


def test_the_last_submit_drops_a_failing_finding_and_keeps_the_rest(tools):
    w, res, _, run = tools
    w.fetch(t.URL, 1, "k1", res)
    problems, f = gate(run, args(BAD_F, GOOD_F), keep=True)
    assert problems == []
    assert [(x["id"], x["sources"][0]["quote"]) for x in f["findings"]] == [("F2", t.QUOTE)]
    assert any(d.startswith("G2 finding 1") for d in f["dropped"]) and "finding 1: no source passed" in f["dropped"][-1]


def test_the_last_submit_drops_a_failing_source_and_keeps_its_finding(tools):
    w, res, _, run = tools
    w.fetch(t.URL, 1, "k1", res)
    claim = "Python 3.14 was released in October 2025 with free threading."
    problems, f = gate(run, args((claim, [(t.URL, BAD), (t.URL, SECOND), (t.OTHER, t.QUOTE)])), keep=True)
    assert problems == [] and [s["quote"] for s in f["findings"][0]["sources"]] == [SECOND]
    assert [d[:2] for d in f["dropped"]] == ["G2", "G1"]          # OTHER was never fetched in this run


def test_a_quote_of_the_wrong_length_is_dropped_on_the_last_submit(tools):
    w, res, _, run = tools
    w.fetch(t.URL, 1, "k1", res)
    problems, f = gate(run, args(GOOD_F, ("A finding with a short quote.", [(t.URL, "released")])), keep=True)
    assert problems == [] and len(f["findings"]) == 1 and "the quote has 8 characters" in f["dropped"][0]


def test_answered_with_no_finding_left_is_still_rejected(tools):
    w, res, _, run = tools
    w.fetch(t.URL, 1, "k1", res)
    problems, f = gate(run, args(BAD_F), keep=True)
    assert f is None and problems[-1].endswith("none had a source that passed")


def test_insufficient_evidence_with_every_finding_dropped_passes(tools):
    w, res, _, run = tools
    w.fetch(t.URL, 1, "k1", res)
    a = args(BAD_F, verdict=st.INSUFFICIENT)
    a["uncertainties"] = ["No page gives the date."]
    problems, f = gate(run, a, keep=True)
    assert problems == [] and f["findings"] == [] and f["dropped"]


def test_any_other_problem_still_rejects_the_last_submit(tools):
    w, res, _, run = tools
    w.fetch(t.URL, 1, "k1", res)
    problems, f = gate(run, args(GOOD_F, ("short", [(t.URL, BAD)])), keep=True)
    assert f is None and any("claim" in p for p in problems) and any(p.startswith("G2") for p in problems)


def test_nothing_dropped_leaves_the_result_as_before(tools):
    w, res, _, run = tools
    w.fetch(t.URL, 1, "k1", res)
    assert gate(run, args(GOOD_F), keep=True) == gate(run, args(GOOD_F), keep=False)
    assert "dropped" not in gate(run, args(GOOD_F), keep=True)[1]


# ---- in a job --------------------------------------------------------------------------------------------------

def submit(id_, *findings):
    return t.call("SubmitFindings", args(*findings), id_)


def test_a_worker_whose_last_submit_has_one_bad_quote_keeps_the_good_finding(tmp_path):
    mixed = (GOOD_F, BAD_F)
    env = t.Env(tmp_path, [t.PLAN, t.SEARCH, t.FETCH, submit("a", *mixed), submit("b", *mixed), submit("c", *mixed),
                           t.REPORT, t.CHECK])
    job = env.start()
    assert job.data["state"] == rr.REPORT_READY and job.data["stages"]["w1"]["status"] == st.ANSWERED
    [w] = json.loads((job.dir / "findings.json").read_text())["workers"]
    assert [x["id"] for x in w["findings"]] == ["W1.F1"] and w["findings"][0]["sources"][0]["quote"] == t.QUOTE
    assert any(d.startswith("G2 finding 2") for d in w["dropped"])
    ev = EventLog(job.runs / job.data["stages"]["w1"]["run_id"] / "events.jsonl").read()
    assert [e["ok"] for e in ev if e["event"] == "findings_checked"] == [False, False, True]
    [d] = [e for e in ev if e["event"] == "findings_dropped"]
    assert d["submit"] == 3


def test_a_worker_with_no_bad_quote_has_no_dropped_list(tmp_path):
    env = t.Env(tmp_path, [t.PLAN, t.SEARCH, t.FETCH, t.SUBMIT, t.REPORT, t.CHECK])
    job = env.start()
    [w] = json.loads((job.dir / "findings.json").read_text())["workers"]
    assert "dropped" not in w
