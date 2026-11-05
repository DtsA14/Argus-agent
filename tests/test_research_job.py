"""SPEC_RESEARCH_JOB PR B: the research job (router/research.py), the planner p1 and the web workers (research/). The model
and DeepSeek Search/Fetch are fakes; the money goes through the real PaidRequests and LLMCaller ledgers."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_drafter as td  # noqa: E402

from harness.events import EventLog  # noqa: E402
from harness.llm import Reservation, reconcile_ledger  # noqa: E402
from harness.paid import PaidRequests  # noqa: E402
from models.fake import StrictScriptedChatModel  # noqa: E402
from research import stages as st  # noqa: E402
from research.web_tools import WebTools  # noqa: E402
from router import job as rj  # noqa: E402
from router import research as rr  # noqa: E402
from runner import load_config  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PRICE = 750_000
URL = "https://docs.python.org/3/whatsnew/3.14.html"
OTHER = "https://example.org/blog/python-314"
PAGE = ("What's New In Python 3.14\n\nPython 3.14 was released on 7 October 2025. Free-threaded Python is now "
        "officially supported, and template string literals (t-strings) were added by PEP 750.")
QUOTE = "Python 3.14 was released on 7 October 2025."
QUESTION = "When was Python 3.14 released, and what are its headline features?"
SUB = "On what date was Python 3.14 released?"


class Spawn:
    """Fake DeepSeek: search answers one result per query, fetch answers PAGE (or `pages[url]`). Counted."""

    def __init__(self, pages=None):
        self.calls, self.pages = [], pages or {URL: PAGE, OTHER: PAGE}

    def __call__(self, kind, args, key, limits):
        self.calls.append((kind, args))
        if kind == "search":
            return {"ok": True, "status": 200, "body": {"results": [{"url": URL, "title": "What's New", "summary": "s"}]}}
        text = self.pages.get(args["url"])
        if text is None:
            return {"ok": False, "reason": "http_error", "status": 404, "error_body": True}
        return {"ok": True, "status": 200, "body": {"title": "", "content": text}}


def cfg():
    c = load_config()
    c["roles"]["researcher"]["model"] = "fake:scripted"
    return c


def call(name, args, id):
    return td.call(name, args, id)


def plan_args(subs=(SUB,), outline=("Release", "Features")):
    return {"sub_questions": [{"question": q, "why": "needed"} for q in subs], "outline": list(outline)}


def findings_args(url=URL, quote=QUOTE, verdict=st.ANSWERED):
    return {"verdict": verdict, "findings": [{"claim": "Python 3.14 was released on 7 October 2025.",
                                              "sources": [{"url": url, "quote": quote}]}],
            "uncertainties": []}


PLAN = call("SubmitPlan", plan_args(), "p")
SEARCH = call("WebSearch", {"query": "python 3.14 release date"}, "s")
FETCH = call("WebFetch", {"url": URL}, "f")
SUBMIT = call("SubmitFindings", findings_args(), "sub")


def report_args(cites=("W1.F1",), text="Python 3.14 was released on 7 October 2025."):
    return {"summary": "Python 3.14 came out in October 2025.",
            "sections": [{"heading": "Release", "paragraphs": [{"text": text, "cites": list(cites)}]}],
            "uncertainties": []}


def check_args(ids=("S", "P1"), verdict="SUPPORTED"):
    return {"verdicts": [{"id": i, "verdict": verdict, "reason": "The quote gives the date."} for i in ids]}


REPORT = call("SubmitReport", report_args(), "rep")
CHECK = call("SubmitCheck", check_args(), "chk")
INSUFFICIENT = call("SubmitFindings", {"verdict": st.INSUFFICIENT, "findings": [],
                                       "uncertainties": ["No page gives the date."]}, "sub")


class Env:
    def __init__(self, tmp_path, script, *, spawn=None, confirm=True):
        self.jobs, self.spawn, self.said, self.confirms = tmp_path / "jobs", spawn or Spawn(), [], []
        self.model = StrictScriptedChatModel(script=list(script))
        self.cfg = cfg()

        def yes(text):
            self.confirms.append(text)
            return confirm
        self.deps = rj.Deps(confirm=yes, get_key=lambda: "unused", isatty=lambda: True,
                            models={"researcher": self.model}, clock=lambda: "2026-11-03T00:00:00Z",
                            echo=self.said.append)
        self.deps.paid = lambda c, log: PaidRequests(c, log, spawn=self.spawn, key="sk-test")

    def start(self, question=QUESTION, **kw):
        return rr.start(question=question, cfg=self.cfg, deps=self.deps, jobs_dir=self.jobs, job_id="jr", **kw)

    def job(self):
        return rj.open_job("jr", self.jobs)


# ---- the whole job ----------------------------------------------------------------------------------------------

def test_a_job_plans_researches_and_keeps_only_gated_findings(tmp_path):
    env = Env(tmp_path, [PLAN, SEARCH, FETCH, SUBMIT, REPORT, CHECK])
    job = env.start()
    assert job.data["state"] == rr.REPORT_READY and len(env.confirms) == 1
    assert "URLs go to deepseek" in env.confirms[0] and "one confirmation covers every stage" in env.confirms[0]
    plan = json.loads((job.dir / "plan.json").read_text())
    assert [q["id"] for q in plan["sub_questions"]] == ["Q1"]
    f = json.loads((job.dir / "findings.json").read_text())
    [w] = f["workers"]
    assert w["verdict"] == st.ANSWERED and w["findings"][0]["id"] == "W1.F1"
    assert w["findings"][0]["sources"][0]["quote"] == QUOTE and w["findings"][0]["sources"][0]["sha256"]
    assert [k for k, _ in env.spawn.calls] == ["search", "fetch"]
    w1 = job.runs / job.data["stages"]["w1"]["run_id"] / "events.jsonl"
    paid = [e for e in reconcile_ledger(EventLog(w1).read())[0]]
    assert sum(r["usd_nano"] for r in paid) >= 2 * PRICE        # the two requests are in the worker's ledger
    assert rj.spent_nano(job) == sum(reconcile_ledger(EventLog(job.runs / s["run_id"] / "events.jsonl").read())[1]
                                     ["usd_nano"] for s in job.data["stages"].values())
    text = rj.status("jr", jobs_dir=env.jobs)
    assert "REPORT_READY (research)" in text and f"Q1 {SUB}" in text and "findings: " in text


def test_not_confirmed_starts_nothing_and_spends_nothing(tmp_path):
    env = Env(tmp_path, [PLAN], confirm=False)
    with pytest.raises(rj.Refused, match="not confirmed"):
        env.start()
    job = env.job()
    assert job.data["state"] == rr.ABANDONED and job.data["stages"] == {} and env.spawn.calls == []
    assert env.model.script == [PLAN]                            # no model call was made


@pytest.mark.parametrize("q", ["too short", "x" * 2001, "   ", None])
def test_a_question_out_of_bounds_creates_no_job(tmp_path, q):
    env = Env(tmp_path, [])
    with pytest.raises(rj.Refused):
        env.start(question=q)
    assert not (env.jobs / "jr").exists()


def test_a_plan_that_never_passes_ends_the_job_without_workers(tmp_path):
    bad = call("SubmitPlan", plan_args(subs=("short",)), "p")
    env = Env(tmp_path, [bad, bad, bad])
    job = env.start()
    assert job.data["state"] == rr.PLAN_FAILED and list(job.data["stages"]) == ["p1"]
    assert env.spawn.calls == [] and job.data["plan"] is None


def test_insufficient_evidence_everywhere_is_inconclusive(tmp_path):
    insufficient = call("SubmitFindings", {"verdict": st.INSUFFICIENT, "findings": [],
                                           "uncertainties": ["No page gives the date."]}, "sub")
    env = Env(tmp_path, [PLAN, insufficient])
    job = env.start()
    assert job.data["state"] == rr.INCONCLUSIVE and job.data["stages"]["w1"]["verdict"] == st.INSUFFICIENT


def test_workers_run_in_plan_order_each_with_its_own_cap(tmp_path):
    two = call("SubmitPlan", plan_args(subs=(SUB, "Which headline features did Python 3.14 add?")), "p")
    env = Env(tmp_path, [two, SEARCH, FETCH, SUBMIT, SEARCH, FETCH, SUBMIT, REPORT, CHECK])
    job = env.start()
    assert list(job.data["stages"]) == ["p1", "w1", "w2", "s1", "e1"] and job.data["state"] == rr.REPORT_READY
    caps = {k: s["cap_usd"] for k, s in job.data["stages"].items()}
    assert caps == {"p1": 0.05, "w1": 0.15, "w2": 0.15, "s1": 0.15, "e1": 0.10}


def test_an_interrupted_worker_is_resumed_and_the_job_finishes(tmp_path, monkeypatch):
    env = Env(tmp_path, [PLAN, SEARCH, FETCH, SUBMIT, REPORT, CHECK])
    real = st.run_worker
    calls = []

    def interrupted(**kw):
        calls.append(kw["resume"])
        if len(calls) == 1:
            raise KeyboardInterrupt
        return real(**kw)
    monkeypatch.setattr(st, "run_worker", interrupted)
    with pytest.raises(KeyboardInterrupt):
        env.start()
    assert env.job().data["state"] == rr.RESEARCHING and "ended_at" not in env.job().data["stages"]["w1"]
    job, _ = rj.resume("jr", cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs)
    assert job.data["state"] == rr.REPORT_READY and calls == [False, False]   # never started: a fresh run


def test_research_states_have_their_own_transitions_and_abandon(tmp_path):
    env = Env(tmp_path, [PLAN, SEARCH, FETCH, SUBMIT, REPORT, CHECK])
    env.start()
    job = env.job()
    with job.lock():
        with pytest.raises(rj.Refused, match="not a legal transition"):
            job.move(rr.PLANNING, env.deps)
    assert rj.abandon("jr", "done", deps=env.deps, jobs_dir=env.jobs).data["state"] == rr.ABANDONED
    with pytest.raises(rj.Refused):
        rj.resume("jr", cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs)


def test_the_cli_starts_a_research_job(tmp_path, capsys):
    sys.path.insert(0, str(ROOT / "scripts"))
    import argus
    env = Env(tmp_path, [PLAN, SEARCH, FETCH, SUBMIT, REPORT, CHECK])
    rc = argus.main(["--jobs-dir", str(env.jobs), "research", "--question", QUESTION], deps=env.deps)
    out = capsys.readouterr().out
    assert rc == 0 and "REPORT_READY (research)" in out


# ---- the planner gate -------------------------------------------------------------------------------------------

@pytest.mark.parametrize("args, part", [
    (plan_args(subs=()), "sub_questions must be a list of 1 to 4"),
    (plan_args(subs=[SUB + str(i) for i in range(5)]), "sub_questions must be a list of 1 to 4"),
    (plan_args(subs=(SUB, SUB)), "two sub-questions are the same"),
    (plan_args(subs=("short",)), "sub-question 1 has 5 characters"),
    (plan_args(outline=()), "outline must be a list"),
    (plan_args(outline=("x" * 121,)), "outline heading 1 has 121"),
    ({"sub_questions": "Q", "outline": ["a"]}, "sub_questions must be a list"),
])
def test_the_planner_gate_refuses_bad_plans(args, part):
    problems, plan = st.plan_gate(args, 4)
    assert plan is None and any(part in p for p in problems), problems


def test_the_harness_numbers_the_sub_questions():
    problems, plan = st.plan_gate(plan_args(subs=(SUB, "Which headline features did Python 3.14 add?")), 4)
    assert problems == [] and [q["id"] for q in plan["sub_questions"]] == ["Q1", "Q2"]


# ---- the worker gate (G1, G2) and its web tools -----------------------------------------------------------------

LIM = load_config()["research_job"]["worker"]


@pytest.fixture
def tools(tmp_path):
    log = EventLog(tmp_path / "e.jsonl")
    spawn = Spawn({URL: PAGE, OTHER: "x" * LIM["part_chars"] + " " + PAGE})
    w = WebTools(tmp_path / "run", PaidRequests(cfg(), log, spawn=spawn, key="k"), log, LIM)
    return w, Reservation(tokens=10**6, usd=1.0), spawn, tmp_path / "run"


def gate(run_dir, **kw):
    return st.findings_gate(findings_args(**kw), run_dir=run_dir, part_chars=LIM["part_chars"])


def test_a_quote_from_a_fetched_and_read_part_passes(tools):
    w, res, _, run = tools
    assert "Python 3.14 was released" in w.fetch(URL, 1, "k1", res)
    problems, f = gate(run)
    assert problems == [] and f["findings"][0]["id"] == "F1"
    assert gate(run, quote=QUOTE.replace(" ", "\n   ", 2))[0] == []


def test_g1_a_url_only_seen_in_search_results_is_refused(tools):
    w, res, _, run = tools
    assert URL in w.search("python 3.14", 8, res)
    problems, _ = gate(run)
    assert any(p.startswith("G1") for p in problems)


@pytest.mark.parametrize("quote", [
    QUOTE.replace("7 October", "8 October"),                    # one word changed
    "ython 3.14 was released on 7 October 2025.",               # starts inside a word
    QUOTE + " Free-threaded Python is now officially sup",      # ends inside a word
    "Python 3.14 was released on 7 October 2025. PEP 750",      # two places joined
])
def test_g2_a_quote_not_on_the_page_as_whole_words_is_refused(tools, quote):
    w, res, _, run = tools
    w.fetch(URL, 1, "k1", res)
    problems, _ = gate(run, quote=quote)
    assert any(p.startswith("G2") for p in problems), problems


def test_g2_a_quote_from_a_part_never_read_is_refused(tools):
    w, res, _, run = tools
    assert "part 1 of 2" in w.fetch(OTHER, 1, "k1", res)
    assert any(p.startswith("G2") for p in gate(run, url=OTHER)[0])
    w.fetch(OTHER, 2, "k2", res)
    assert gate(run, url=OTHER)[0] == []


def test_a_kept_search_or_page_is_never_bought_again(tools):
    w, res, spawn, _ = tools
    w.search("python 3.14", 8, res)
    w.search("python 3.14", 8, res)
    w.fetch(URL, 1, "k1", res)
    w.fetch(URL, 1, "k2", res)
    assert [k for k, _ in spawn.calls] == ["search", "fetch"] and res.used_nano == 2 * PRICE


def test_search_and_fetch_limits_count_requests_not_kept_answers(tools):
    w, res, spawn, _ = tools
    for i in range(LIM["max_searches"]):
        w.search(f"query {i}", 8, res)
    assert "its limit" in w.search("one more", 8, res)
    assert URL in w.search("query 0", 8, res)              # a kept answer is still given, free
    assert len(spawn.calls) == LIM["max_searches"] and res.used_nano == LIM["max_searches"] * PRICE


def test_a_refused_url_or_query_is_never_counted_or_sent(tools):
    w, res, spawn, run = tools
    assert w.fetch("http://127.0.0.1/", 1, "k", res).startswith("Refused")
    assert w.search("", 8, res).startswith("Refused")
    assert spawn.calls == [] and not (run / "web" / "requests.jsonl").exists()


def test_a_definite_fetch_error_is_kept_and_not_paid_again(tools):
    w, res, spawn, _ = tools
    url = "https://example.org/missing"
    assert w.fetch(url, 1, "k1", res).startswith("Refused")
    assert w.fetch(url, 1, "k2", res).startswith("Refused")
    assert len(spawn.calls) == 1 and res.used_nano == 0


def test_web_text_per_run_is_limited(tmp_path):
    log = EventLog(tmp_path / "e.jsonl")
    lim = {**LIM, "attempt_text": len(PAGE) + 10}
    w = WebTools(tmp_path / "run", PaidRequests(cfg(), log, spawn=Spawn(), key="k"), log, lim)
    res = Reservation(tokens=10**6, usd=1.0)
    assert "Python 3.14" in w.fetch(URL, 1, "k1", res)
    assert "no room left" in w.fetch(OTHER, 1, "k2", res)     # a second page would pass the run's web text
    assert "Python 3.14" in w.fetch(URL, 1, "k1", res)        # the same tool step again: not counted twice


def test_the_worker_toolbox_offers_only_search_fetch_and_submit(tmp_path):
    env = Env(tmp_path, [PLAN, call("ReadFile", {"path": "x"}, "r"), call("RunValidation", {"id": "v"}, "v"), SEARCH,
                         FETCH, INSUFFICIENT])          # the job ends after the worker: its tools are the last bound
    job = env.start()
    assert job.data["state"] == rr.INCONCLUSIVE
    answers = [str(m.content) for m in env.model.calls[4]["messages"] if type(m).__name__ == "ToolMessage"]
    assert answers[0].startswith("Refused: ReadFile is not offered")
    assert answers[1].startswith("Refused: RunValidation is not offered")
    assert {t.__name__ for t in env.model.bound_tools} == {"WebSearch", "WebFetch", "SubmitFindings"}


# ---- crash-resume of a worker across processes ------------------------------------------------------------------

PROC = ("import sys; sys.path[:0] = [sys.argv[1], sys.argv[1] + '/tests']; import test_research_job as t; "
        "sys.exit(t._proc(*sys.argv[2:]))")


def _proc(runs, crash_at, resume, spawned):
    spawn = Spawn()

    def counted(kind, args, key, limits):
        with open(spawned, "a") as f:
            f.write(kind + "\n")
        return spawn(kind, args, key, limits)
    r = st.run_worker(run_id="wc", runs_dir=runs, cfg=rj.stage_config(cfg(), 0.15), question=QUESTION,
                      sub={"id": "Q1", "question": SUB, "why": ""}, max_usd=0.15, resume=resume == "1",
                      crash_at=None if crash_at == "-" else crash_at,
                      paid=lambda c, log: PaidRequests(c, log, spawn=counted, key="k"))
    return 0 if r["status"] == st.ANSWERED else 1


def _script(name, args, id):
    return {"tool_calls": [{"name": name, "args": args, "id": id}], "usage": {"input_tokens": 500, "output_tokens": 60}}


@pytest.mark.parametrize("point", ["worker@after_llm", "worker@after_tool:WebSearch", "worker@after_tool:WebFetch",
                                   "worker@after_tool:SubmitFindings", "work@after_commit"])
def test_a_crashed_worker_resumes_without_buying_again(tmp_path, point):
    script = [_script("WebSearch", {"query": "python 3.14 release date"}, "s"), _script("WebFetch", {"url": URL}, "f"),
              _script("SubmitFindings", findings_args(), "sub")]
    if point == "worker@after_llm":
        script.insert(0, script[0])                  # step 0's reply was not committed: it is bought again
    (tmp_path / "script.json").write_text(json.dumps(script))
    env = {**os.environ, "ARGUS_FAKE_SCRIPT": str(tmp_path / "script.json")}

    def go(crash, resume):
        return subprocess.run([sys.executable, "-c", PROC, str(ROOT), str(tmp_path / "runs"), crash, resume,
                               str(tmp_path / "spawned.log")], cwd=ROOT, capture_output=True, text=True, env=env,
                              timeout=300)
    r1 = go(point, "0")
    assert r1.returncode == 42, (r1.stdout[-2000:], r1.stderr[-2000:])
    r2 = go("-", "1")
    assert r2.returncode == 0, (r2.stdout[-2000:], r2.stderr[-2000:])
    spawned = (tmp_path / "spawned.log").read_text().splitlines()
    assert spawned == ["search", "fetch"]            # each request bought once, crash or not
    evs = [json.loads(line) for line in (tmp_path / "runs" / "wc" / "events.jsonl").read_text().splitlines()]
    i = next(n for n, e in enumerate(evs) if e["event"] == "crash_simulated")
    committed = {e["step"] for e in evs[:i] if e["event"] == "step_committed" and e["kind"] == "llm"}
    rebought = {e["step"] for e in evs[i:] if e["event"] == "llm_call" and e.get("status") == "ok"
                and e.get("role") == "researcher"}
    assert not committed & rebought
    _, totals = reconcile_ledger(evs)
    assert totals["unknown_after_crash"] == 0


# ---- added from the mutants -------------------------------------------------------------------------------------

def test_fetches_per_run_are_limited(tools):
    w, res, spawn, _ = tools
    for i in range(LIM["max_fetches"]):
        w.fetch(f"https://example.org/p{i}", 1, f"k{i}", res)
    assert "its limit" in w.fetch("https://example.org/one-more", 1, "kx", res)
    assert len(spawn.calls) == LIM["max_fetches"]


def test_answered_needs_a_finding_and_insufficient_needs_an_uncertainty(tools):
    _, _, _, run = tools
    problems, _ = st.findings_gate({"verdict": st.ANSWERED, "findings": [], "uncertainties": []}, run_dir=run,
                                   part_chars=LIM["part_chars"])
    assert any("needs at least one finding" in p for p in problems)
    problems, _ = st.findings_gate({"verdict": st.INSUFFICIENT, "findings": [], "uncertainties": []}, run_dir=run,
                                   part_chars=LIM["part_chars"])
    assert any("needs at least one uncertainty" in p for p in problems)


def test_a_resume_does_not_run_a_finished_worker_again(tmp_path, monkeypatch):
    two = call("SubmitPlan", plan_args(subs=(SUB, "Which headline features did Python 3.14 add?")), "p")
    env = Env(tmp_path, [two, SEARCH, FETCH, SUBMIT, SEARCH, FETCH, SUBMIT, REPORT, CHECK])
    real = st.run_worker
    seen = []

    def interrupted(**kw):
        seen.append(kw["sub"]["id"])
        if seen == ["Q1", "Q2"]:
            raise KeyboardInterrupt
        return real(**kw)
    monkeypatch.setattr(st, "run_worker", interrupted)
    with pytest.raises(KeyboardInterrupt):
        env.start()
    rj.resume("jr", cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs)
    assert seen == ["Q1", "Q2", "Q2"] and env.job().data["state"] == rr.REPORT_READY


def test_every_research_graph_runs_with_sync_checkpoints():
    import re
    for path in sorted((ROOT / "research").glob("*.py")):
        for call_ in re.findall(r"graph\.invoke\([^\n]*", path.read_text(encoding="utf-8")):
            assert 'durability="sync"' in call_, (path.name, call_)


def test_a_committed_rejected_submit_is_replayed_never_gated_again(tmp_path):
    bad = findings_args(url=OTHER)                       # never fetched: G1 rejects it
    script = [_script("SubmitFindings", bad, "b"), _script("WebFetch", {"url": URL}, "f"),
              _script("WebFetch", {"url": URL}, "f"), _script("SubmitFindings", findings_args(), "sub")]
    (tmp_path / "script.json").write_text(json.dumps(script))
    env = {**os.environ, "ARGUS_FAKE_SCRIPT": str(tmp_path / "script.json")}

    def go(crash, resume):
        return subprocess.run([sys.executable, "-c", PROC, str(ROOT), str(tmp_path / "runs"), crash, resume,
                               str(tmp_path / "spawned.log")], cwd=ROOT, capture_output=True, text=True, env=env,
                              timeout=300)
    assert go("worker@after_tool:WebFetch", "0").returncode == 42   # step 1's fetch ran but was not committed
    r = go("-", "1")
    assert r.returncode == 0, r.stderr[-2000:]
    evs = [json.loads(line) for line in (tmp_path / "runs" / "wc" / "events.jsonl").read_text().splitlines()]
    checked = [e for e in evs if e["event"] == "findings_checked"]
    assert [c["submit"] for c in checked] == [1, 2]      # submit 1 was gated once, before the crash


# ---- added from the code review --------------------------------------------------------------------------------

def test_a_provider_failure_in_a_worker_blocks_the_job_and_keeps_the_findings_so_far(tmp_path):
    from models.fake import FakeHTTPError
    two = call("SubmitPlan", plan_args(subs=(SUB, "Which headline features did Python 3.14 add?")), "p")
    env = Env(tmp_path, [two, SEARCH, FETCH, SUBMIT, FakeHTTPError(400, "bad request")])
    job = env.start()
    assert job.data["state"] == rr.BLOCKED and "w2" in job.data["stages"]
    f = json.loads((job.dir / "findings.json").read_text())
    assert [w["stage"] for w in f["workers"]] == ["w1", "w2"] and f["workers"][0]["findings"][0]["id"] == "W1.F1"
    assert f["workers"][1]["findings"] == []


def test_a_job_cap_that_runs_out_mid_way_keeps_the_findings_paid_for(tmp_path, monkeypatch):
    two = call("SubmitPlan", plan_args(subs=(SUB, "Which headline features did Python 3.14 add?")), "p")
    env = Env(tmp_path, [two, SEARCH, FETCH, SUBMIT])
    # the fake model costs next to nothing: what is left of the job after w1 is set to less than w2's cap
    monkeypatch.setattr(rj, "left_usd", lambda job: 0.10 if job.data["stages"].get("w1", {}).get("ended_at") else 1.0)
    with pytest.raises(rj.Refused, match="BLOCKED"):
        env.start()
    job = env.job()
    f = json.loads((job.dir / "findings.json").read_text())
    assert job.data["state"] == rr.BLOCKED and [w["stage"] for w in f["workers"]] == ["w1"]


@pytest.mark.parametrize("cap", [float("inf"), float("nan"), 0.1, 0.0, -1.0])
def test_a_cap_that_cannot_fund_the_planner_and_one_worker_creates_no_job(tmp_path, cap):
    env = Env(tmp_path, [PLAN])
    with pytest.raises(rj.Refused, match="no job was created"):
        env.start(max_usd=cap)
    assert env.confirms == [] and not (env.jobs / "jr").exists()


def test_web_settings_are_checked_before_the_confirmation(tmp_path):
    env = Env(tmp_path, [PLAN])
    env.cfg["web_research"]["price_usd_per_request"].pop("fetch")
    with pytest.raises(rj.Refused, match="has no fetch"):
        env.start()
    env.cfg = cfg()
    env.cfg["web_research"]["provider"] = "nowhere"
    with pytest.raises(rj.Refused, match="not a configured provider"):
        env.start()
    env.cfg = cfg()
    env.cfg["roles"]["researcher"]["model"] = "deepseek:unpriced-model"
    with pytest.raises(rj.Refused, match="no price"):
        env.start()
    assert env.confirms == [] and env.model.script == [PLAN]


def test_a_request_the_reservation_cannot_pay_is_not_counted(tmp_path):
    log = EventLog(tmp_path / "e.jsonl")
    w = WebTools(tmp_path / "run", PaidRequests(cfg(), log, spawn=Spawn(), key="k"), log, LIM)
    poor = Reservation(tokens=10**6, usd=0.0005)
    assert "budget" in w.search("python 3.14", 8, poor) and "budget" in w.fetch(URL, 1, "k", poor)
    assert not (tmp_path / "run" / "web" / "requests.jsonl").exists()


def test_a_page_with_no_room_left_to_serve_is_not_bought(tmp_path):
    log = EventLog(tmp_path / "e.jsonl")
    spawn = Spawn()
    w = WebTools(tmp_path / "run", PaidRequests(cfg(), log, spawn=spawn, key="k"), log,
                 {**LIM, "attempt_text": LIM["part_chars"] + 50})
    res = Reservation(tokens=10**6, usd=1.0)
    w.fetch(URL, 1, "k1", res)
    assert "no room left" in w.fetch(OTHER, 1, "k2", res)
    assert [a["url"] for k, a in spawn.calls] == [URL] and res.used_nano == PRICE


CONFIG = json.dumps({"docsConfig": {"name": "Docs", "nav": ["page %d" % i for i in range(1500)]}})


def test_a_page_of_site_config_then_the_article_serves_the_article_first(tmp_path):
    log = EventLog(tmp_path / "e.jsonl")
    spawn = Spawn({URL: "Persistence - Docs\n\n" + CONFIG + "\n" + PAGE})
    w = WebTools(tmp_path / "run", PaidRequests(cfg(), log, spawn=spawn, key="k"), log, LIM)
    out = w.fetch(URL, 1, "k1", Reservation(tokens=10**6, usd=1.0))
    assert len(CONFIG) > LIM["part_chars"] and "part 1 of 1" in out and QUOTE in out and "docsConfig" not in out
    assert gate(tmp_path / "run")[0] == []


def test_a_page_of_only_site_config_is_an_empty_page_and_uses_no_web_text(tmp_path):
    log = EventLog(tmp_path / "e.jsonl")
    w = WebTools(tmp_path / "run", PaidRequests(cfg(), log, spawn=Spawn({URL: CONFIG}), key="k"), log, LIM)
    assert "empty page" in w.fetch(URL, 1, "k1", Reservation(tokens=10**6, usd=1.0))
    assert not (tmp_path / "run" / "web" / "served_1.jsonl").exists()


@pytest.mark.parametrize("line", ["x" * 3000, "{" + "x" * 3000, '{"a": 1}', "[1, 2] " + "y" * 3000])
def test_a_long_line_that_is_not_one_json_value_is_kept(tmp_path, line):
    log = EventLog(tmp_path / "e.jsonl")
    w = WebTools(tmp_path / "run", PaidRequests(cfg(), log, spawn=Spawn({URL: line + "\n" + PAGE}), key="k"), log,
                 {**LIM, "part_chars": 10**5})
    assert line in w.fetch(URL, 1, "k1", Reservation(tokens=10**6, usd=1.0))


def test_another_part_of_a_kept_page_still_respects_the_text_limit(tmp_path):
    log = EventLog(tmp_path / "e.jsonl")
    spawn = Spawn({OTHER: "x" * LIM["part_chars"] + " " + PAGE})
    w = WebTools(tmp_path / "run", PaidRequests(cfg(), log, spawn=spawn, key="k"), log,
                 {**LIM, "attempt_text": LIM["part_chars"] + 50})
    res = Reservation(tokens=10**6, usd=1.0)
    assert "part 1 of 2" in w.fetch(OTHER, 1, "k1", res)
    assert "would pass its limit" in w.fetch(OTHER, 2, "k2", res)     # kept page: no purchase, still no text
    assert len(spawn.calls) == 1
