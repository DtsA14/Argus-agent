"""SPEC_RESEARCH_JOB PR C: the synthesis s1, the claim checker e1 and REPORT.md (research/report.py, router/research.py).
The model and DeepSeek Search/Fetch are fakes, as in test_research_job.py, whose helpers this file uses."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_research_job as t  # noqa: E402

from harness.llm import reconcile_ledger  # noqa: E402
from models.fake import FakeHTTPError  # noqa: E402
from research import report as rp  # noqa: E402
from router import job as rj  # noqa: E402
from router import research as rr  # noqa: E402

ROOT = t.ROOT
Env, call, PLAN, SEARCH, FETCH, SUBMIT, REPORT, CHECK = (t.Env, t.call, t.PLAN, t.SEARCH, t.FETCH, t.SUBMIT, t.REPORT,
                                                         t.CHECK)
FEATURES = "Free-threaded Python is now officially supported"
Q2 = {"id": "Q2", "question": "Which headline features did Python 3.14 add?", "why": ""}
FINDINGS = {"question": t.QUESTION,
            "plan": {"sub_questions": [{"id": "Q1", "question": t.SUB, "why": ""}, Q2], "outline": ["Release"]},
            "workers": [
                {"stage": "w1", "sub_question": {"id": "Q1", "question": t.SUB, "why": ""}, "status": "ANSWERED",
                 "verdict": "ANSWERED", "uncertainties": [], "findings": [
                     {"id": "W1.F1", "claim": "Python 3.14 was released on 7 October 2025.",
                      "sources": [{"url": t.URL, "quote": t.QUOTE, "title": "What's New",
                                   "fetched_at": "2026-11-03T00:00:00Z", "sha256": "a" * 64}]},
                     {"id": "W1.F2", "claim": "Free-threaded Python is officially supported in 3.14.",
                      "sources": [{"url": t.OTHER, "quote": FEATURES, "title": "",
                                   "fetched_at": "2026-11-03T00:00:01Z", "sha256": "b" * 64}]}]},
                {"stage": "w2", "sub_question": Q2, "status": "INSUFFICIENT_EVIDENCE",
                 "verdict": "INSUFFICIENT_EVIDENCE", "findings": [], "uncertainties": ["No page lists the features."]}]}
KNOWN = set(rp.citable(FINDINGS))
WORKED = [PLAN, SEARCH, FETCH, SUBMIT]


def report(**kw):
    return t.report_args(**kw)


# ---- the whole job ----------------------------------------------------------------------------------------------

def test_a_job_ends_with_a_report_the_harness_renders_and_e1_flags(tmp_path):
    env = Env(tmp_path, WORKED + [REPORT, CHECK])
    job = env.start()
    assert job.data["state"] == rr.REPORT_READY and len(env.confirms) == 1
    assert "synthesis $0.15" in env.confirms[0] and "claim checker $0.10" in env.confirms[0]
    md = (job.dir / "REPORT.md").read_text()
    assert "Python 3.14 was released on 7 October 2025. [1]" in md
    assert f"<{t.URL}>" in md and f"> {t.QUOTE}" in md and "*e1: SUPPORTED (The quote gives the date.)*" in md
    page = json.loads((job.runs / job.data["stages"]["w1"]["run_id"] / "result.json").read_text())
    assert page["findings"]["findings"][0]["sources"][0]["sha256"] in md
    assert json.loads((job.dir / "report.json").read_text())["sections"][0]["paragraphs"][0]["id"] == "P1"
    assert json.loads((job.dir / "check.json").read_text())["status"] == rp.CHECKED
    text = rj.status("jr", jobs_dir=env.jobs)
    assert "REPORT_READY (research)" in text and "e1 flags: 2 supported, 0 partial, 0 unsupported" in text
    assert env.model.script == []


def test_the_checker_sees_the_quotes_each_item_cites(tmp_path):
    env = Env(tmp_path, WORKED + [REPORT, CHECK])
    env.start()
    prompt = "\n".join(str(m.content) for m in env.model.calls[-1]["messages"])
    assert "[P1] Python 3.14 was released on 7 October 2025." in prompt and t.QUOTE in prompt and "[S]" in prompt


def test_synthesis_and_checker_have_no_web(tmp_path):
    env = Env(tmp_path, WORKED + [SEARCH, REPORT, FETCH, CHECK])
    job = env.start()
    assert job.data["state"] == rr.REPORT_READY and len(env.spawn.calls) == 2      # the worker's two requests only
    answers = [str(m.content) for c in env.model.calls for m in c["messages"] if type(m).__name__ == "ToolMessage"]
    assert any("Refused: WebSearch is not offered" in a for a in answers)
    assert any("Refused: WebFetch is not offered" in a for a in answers)
    assert [x.__name__ for x in env.model.bound_tools] == ["SubmitCheck"]


def test_unsupported_flags_never_fail_the_job(tmp_path):
    env = Env(tmp_path, WORKED + [REPORT, call("SubmitCheck", t.check_args(verdict=rp.UNSUPPORTED), "c")])
    job = env.start()
    assert job.data["state"] == rr.REPORT_READY
    assert "*e1: UNSUPPORTED" in (job.dir / "REPORT.md").read_text()
    assert "e1 flags: 0 supported, 0 partial, 2 unsupported" in rj.status("jr", jobs_dir=env.jobs)


def test_a_report_that_never_passes_ends_the_job_without_a_check(tmp_path):
    bad = call("SubmitReport", report(cites=("W1.F9",)), "r")
    env = Env(tmp_path, WORKED + [bad, bad, bad])
    job = env.start()
    assert job.data["state"] == rr.SYNTHESIS_FAILED and "e1" not in job.data["stages"]
    assert not (job.dir / "REPORT.md").exists() and (job.dir / "findings.json").exists()
    assert env.model.script == []


def test_a_checker_that_never_passes_leaves_the_report_marked_not_checked(tmp_path):
    bad = call("SubmitCheck", t.check_args(ids=("P1",)), "c")                       # S has no verdict
    env = Env(tmp_path, WORKED + [REPORT, bad, bad, bad])
    job = env.start()
    assert job.data["state"] == rr.REPORT_READY
    assert json.loads((job.dir / "check.json").read_text())["status"] == rp.NOT_CHECKED
    md = (job.dir / "REPORT.md").read_text()
    assert "did not check this report: submits_exhausted" in md and "*e1:" not in md
    assert "(not checked by e1)" in rj.status("jr", jobs_dir=env.jobs)


def test_a_checker_provider_failure_blocks_and_keeps_the_unchecked_report(tmp_path):
    env = Env(tmp_path, WORKED + [REPORT, FakeHTTPError(400, "bad request")])
    job = env.start()
    assert job.data["state"] == rr.BLOCKED
    md = (job.dir / "REPORT.md").read_text()
    assert "Python 3.14 was released on 7 October 2025. [1]" in md and "*e1:" not in md


def test_a_synthesis_provider_failure_blocks_without_a_report(tmp_path):
    env = Env(tmp_path, WORKED + [FakeHTTPError(400, "bad request")])
    job = env.start()
    assert job.data["state"] == rr.BLOCKED and not (job.dir / "REPORT.md").exists()


def test_an_inconclusive_job_is_not_synthesized(tmp_path):
    env = Env(tmp_path, [PLAN, t.INSUFFICIENT])
    job = env.start()
    assert job.data["state"] == rr.INCONCLUSIVE and list(job.data["stages"]) == ["p1", "w1"]
    assert not (job.dir / "REPORT.md").exists()


@pytest.mark.parametrize("cap", [0.89, 0.5])
def test_a_cap_that_cannot_fund_every_stage_creates_no_job(tmp_path, cap):
    env = Env(tmp_path, [PLAN])
    with pytest.raises(rj.Refused, match="the synthesis and the checker"):
        env.start(max_usd=cap)
    assert env.confirms == [] and not (env.jobs / "jr").exists()


def test_a_cap_that_funds_every_stage_exactly_starts(tmp_path):
    env = Env(tmp_path, WORKED + [REPORT, CHECK])
    assert env.start(max_usd=0.90).data["state"] == rr.REPORT_READY


# ---- the gates --------------------------------------------------------------------------------------------------

def test_a_good_report_passes_and_the_harness_numbers_the_paragraphs():
    args = report()
    args["sections"].append({"heading": "Features", "paragraphs": [{"text": "It supports free threading.",
                                                                   "cites": ["W1.F2"]},
                                                                  {"text": "Both.", "cites": ["W1.F1", "W1.F2"]}]})
    problems, r = rp.report_gate(args, KNOWN)
    assert problems == [] and [p["id"] for s in r["sections"] for p in s["paragraphs"]] == ["P1", "P2", "P3"]


@pytest.mark.parametrize("change, problem", [
    (lambda a: a["sections"][0]["paragraphs"][0].update(cites=["W1.F9"]), "not findings in the list"),
    (lambda a: a["sections"][0]["paragraphs"][0].update(cites=[]), "needs 1 to"),
    (lambda a: a["sections"][0]["paragraphs"][0].update(cites=["W1.F1", "W1.F1"]), "cites a finding twice"),
    (lambda a: a["sections"][0]["paragraphs"][0].update(text="See https://evil.example/x for more."), "URL"),
    (lambda a: a["sections"][0]["paragraphs"][0].update(text="See www.example.com for more."), "URL"),
    (lambda a: a["sections"][0]["paragraphs"][0].update(text="Mail mailto:x@y.org now."), "URL"),
    (lambda a: a["sections"][0]["paragraphs"][0].update(text="[x](javascript:alert(1))"), "URL"),
    (lambda a: a["sections"][0]["paragraphs"][0].update(text="![x](//10.0.0.1/beacon)"), "URL"),
    (lambda a: a["sections"][0]["paragraphs"][0].update(text="see <img src=a>"), "HTML"),
    (lambda a: a["sections"][0]["paragraphs"][0].update(text="[click] (evil)"), "URL"),
    (lambda a: a["sections"][0]["paragraphs"][0].update(text="It is true [2]."), "bracketed number"),
    (lambda a: a["sections"][0]["paragraphs"][0].update(text="[a](ftp://x)"), "URL"),
    (lambda a: a.update(summary="Read http://x.org first."), "summary has a link"),
    (lambda a: a["sections"][0].update(heading="From https://x.org"), "heading has a link"),
    (lambda a: a.update(uncertainties=["www.x.org was down"]), "uncertainty 1 has a link"),
    (lambda a: a["sections"][0].update(paragraphs=[]), "at least one paragraph"),
    (lambda a: a.update(sections=[]), "sections must be a list of 1"),
    (lambda a: a.update(summary=""), "summary has 0 characters"),
    (lambda a: a["sections"][0]["paragraphs"][0].update(text="x" * (rp.TEXT_MAX + 1)), "paragraph 1 has"),
    (lambda a: a["sections"][0].update(paragraphs=[{"text": "ok", "cites": ["W1.F1"]}] * (rp.PARAGRAPHS_MAX + 1)),
     f"at most {rp.PARAGRAPHS_MAX}"),
])
def test_the_report_gate_refuses(change, problem):
    args = report()
    change(args)
    problems, r = rp.report_gate(args, KNOWN)
    assert r is None and any(problem in p for p in problems), problems


def test_a_report_lists_only_the_findings_it_cites():
    _, r = rp.report_gate(report(cites=("W1.F2",), text="It supports free threading."), KNOWN)
    md = rp.render(FINDINGS, r)
    assert f"<{t.OTHER}>" in md and t.URL not in md and t.QUOTE not in md and "[1] W1.F2:" in md
    assert "Not checked yet" in md and "Not answered: Q2" in md and "No page lists the features." in md


@pytest.mark.parametrize("args, problem", [
    (t.check_args(ids=("P1",)), "no verdict for ['S']"),
    (t.check_args(ids=("S", "P1", "P1")), "has a verdict already"),
    (t.check_args(ids=("S", "P1", "P7")), "unknown item 'P7'"),
    (t.check_args(verdict="TRUE"), "verdict must be one of"),
    ({"verdicts": [{"id": "S", "verdict": "SUPPORTED", "reason": "x" * 301},
                   {"id": "P1", "verdict": "SUPPORTED", "reason": "ok"}]}, "reason has 301"),
    ({"verdicts": [{"id": "S", "verdict": "SUPPORTED"}, {"id": "P1", "verdict": "SUPPORTED", "reason": "ok"}]},
     "reason must be text"),
    ({"verdicts": "all supported"}, "must be a list"),
])
def test_the_check_gate_wants_one_verdict_per_item(args, problem):
    problems, v = rp.check_gate(args, ["S", "P1"])
    assert v is None and any(problem in p for p in problems), problems


def test_the_summary_is_checked_against_everything_the_report_cites():
    args = report()
    args["sections"].append({"heading": "Features", "paragraphs": [{"text": "Free threading.", "cites": ["W1.F2"]}]})
    _, r = rp.report_gate(args, KNOWN)
    items = rp.check_items(r)
    assert [i["id"] for i in items] == ["S", "P1", "P2"] and items[0]["cites"] == ["W1.F1", "W1.F2"]
    assert rp.check_gate(t.check_args(ids=("S", "P1", "P2")), [i["id"] for i in items])[0] == []


# ---- crash-resume ----------------------------------------------------------------------------------------------

def test_a_finished_synthesis_not_yet_recorded_is_not_bought_again(tmp_path, monkeypatch):
    env = Env(tmp_path, WORKED + [REPORT, CHECK])
    real, seen = rp.run_synthesis, []

    def ends_then_dies(**kw):
        seen.append(kw["resume"])
        r = real(**kw)
        if len(seen) == 1:
            raise KeyboardInterrupt                        # the run committed its result; the job never recorded it
        return r
    monkeypatch.setattr(rp, "run_synthesis", ends_then_dies)
    with pytest.raises(KeyboardInterrupt):
        env.start()
    assert env.job().data["state"] == rr.SYNTHESIZING
    job, _ = rj.resume("jr", cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs)
    assert job.data["state"] == rr.REPORT_READY and seen == [False, True] and env.model.script == []
    s1 = job.runs / job.data["stages"]["s1"]["run_id"] / "events.jsonl"
    assert reconcile_ledger(t.EventLog(s1).read())[1]["calls"] == 1             # the report was bought once


def test_a_resume_after_the_synthesis_runs_only_the_checker(tmp_path, monkeypatch):
    env = Env(tmp_path, WORKED + [REPORT, CHECK])
    real_s, real_c, seen = rp.run_synthesis, rp.run_check, []

    def s1(**kw):
        seen.append("s1")
        return real_s(**kw)

    def e1(**kw):
        seen.append("e1")
        if seen.count("e1") == 1:
            raise KeyboardInterrupt
        return real_c(**kw)
    monkeypatch.setattr(rp, "run_synthesis", s1)
    monkeypatch.setattr(rp, "run_check", e1)
    with pytest.raises(KeyboardInterrupt):
        env.start()
    assert env.job().data["state"] == rr.CHECKING and (env.job().dir / "REPORT.md").exists()
    job, _ = rj.resume("jr", cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs)
    assert job.data["state"] == rr.REPORT_READY and seen == ["s1", "e1", "e1"]


PROC = ("import sys; sys.path[:0] = [sys.argv[1], sys.argv[1] + '/tests']; import test_research_report as t; "
        "sys.exit(t._proc(*sys.argv[2:]))")


def _proc(runs, stage, crash_at, resume):
    common = dict(runs_dir=runs, cfg=rj.stage_config(t.cfg(), 0.15), findings=FINDINGS, max_usd=0.15,
                  resume=resume == "1", crash_at=None if crash_at == "-" else crash_at)
    if stage == "s1":
        r = rp.run_synthesis(run_id="sc", **common)
        return 0 if r["status"] == rp.REPORTED else 1
    _, rep = rp.report_gate(report(), KNOWN)
    r = rp.run_check(run_id="cc", report=rep, **common)
    return 0 if r["status"] == rp.CHECKED else 1


@pytest.mark.parametrize("stage, point", [("s1", "report@after_llm"), ("s1", "report@after_tool:SubmitReport"),
                                          ("s1", "work@after_commit"), ("e1", "check@after_llm"),
                                          ("e1", "check@after_tool:SubmitCheck"), ("e1", "work@after_commit")])
def test_a_crashed_synthesis_or_check_resumes_without_buying_again(tmp_path, stage, point):
    reply = t._script("SubmitReport", report(), "r") if stage == "s1" else t._script("SubmitCheck", t.check_args(), "c")
    script = [reply, reply] if point.endswith("after_llm") else [reply]    # an uncommitted reply is bought again
    (tmp_path / "script.json").write_text(json.dumps(script))
    env = {**os.environ, "ARGUS_FAKE_SCRIPT": str(tmp_path / "script.json")}

    def go(crash, resume):
        return subprocess.run([sys.executable, "-c", PROC, str(ROOT), str(tmp_path / "runs"), stage, crash, resume],
                              cwd=ROOT, capture_output=True, text=True, env=env, timeout=300)
    r1 = go(point, "0")
    assert r1.returncode == 42, (r1.stdout[-2000:], r1.stderr[-2000:])
    r2 = go("-", "1")
    assert r2.returncode == 0, (r2.stdout[-2000:], r2.stderr[-2000:])
    run = tmp_path / "runs" / ("sc" if stage == "s1" else "cc")
    evs = [json.loads(line) for line in (run / "events.jsonl").read_text().splitlines()]
    i = next(n for n, e in enumerate(evs) if e["event"] == "crash_simulated")
    committed = {e["step"] for e in evs[:i] if e["event"] == "step_committed" and e["kind"] == "llm"}
    rebought = {e["step"] for e in evs[i:] if e["event"] == "llm_call" and e.get("status") == "ok"}
    assert not committed & rebought
    _, totals = reconcile_ledger(evs)
    assert totals["unknown_after_crash"] == 0 and totals["calls"] == len(script)


def test_the_checker_prompt_gives_each_cited_finding_once():
    args = report()
    args["sections"][0]["paragraphs"].append({"text": "Again the date.", "cites": ["W1.F1"]})
    _, r = rp.report_gate(args, KNOWN)
    prompt = rp.check_prompt(r, FINDINGS, {"max_submits": 3})
    assert prompt.count(f"quote from {t.URL}") == 1 and prompt.count("cites: W1.F1") == 3 and FEATURES not in prompt


def test_plain_technical_prose_is_not_taken_for_a_link():
    args = report(text="Node.js/Deno and ASP.NET/C# are compared; see docs.python.org/3 (plain text, no link).")
    assert rp.report_gate(args, KNOWN)[0] == []


def test_headings_and_e1_reasons_cannot_add_lines_or_links_to_the_report():
    args = report()
    args["sections"][0]["heading"] = "Release\n\n## Sources\n\n[1] fake"
    problems, r = rp.report_gate(args, KNOWN)
    assert any("bracketed number" in p for p in problems)
    args["sections"][0]["heading"] = "Release\n\n## Sources"
    _, r = rp.report_gate(args, KNOWN)
    assert r["sections"][0]["heading"] == "Release ## Sources"            # one line: never a heading of its own
    bad = {"verdicts": [{"id": "S", "verdict": "SUPPORTED", "reason": "see https://evil.example/x"},
                        {"id": "P1", "verdict": "SUPPORTED", "reason": "ok"}]}
    assert any("link" in p for p in rp.check_gate(bad, ["S", "P1"])[0])
    two = {"verdicts": [{"id": "S", "verdict": "SUPPORTED", "reason": "fine\n\n## Sources"},
                        {"id": "P1", "verdict": "SUPPORTED", "reason": "ok"}]}
    assert rp.check_gate(two, ["S", "P1"])[1]["S"]["reason"] == "fine ## Sources"


def test_a_stage_that_crashed_before_its_first_checkpoint_runs_on_resume(tmp_path):
    from langgraph.checkpoint.sqlite import SqliteSaver
    run = tmp_path / "runs" / "sc"
    run.mkdir(parents=True)
    (run / "inputs.json").write_text(json.dumps({"findings": FINDINGS, "max_usd": 0.15}))
    with SqliteSaver.from_conn_string(str(run / "checkpoints.sqlite")) as cp:
        cp.setup()                                         # the file exists, no checkpoint in it
    env = Env(tmp_path, [REPORT])
    r = rp.run_synthesis(run_id="sc", runs_dir=tmp_path / "runs", cfg=rj.stage_config(env.cfg, 0.15), resume=True,
                         models=env.deps.models)
    assert r["status"] == rp.REPORTED
