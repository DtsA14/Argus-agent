"""SPEC_RESEARCH_STAGE: the research stage r1. Read-only tools and ReadDocs, a SubmitHandoff the harness gates (G1 every
url downloaded in this run, G2 every quote in that page's text, G3 the installed version), INSUFFICIENT_EVIDENCE as an
outcome, and a human research-ok before the drafter. The downloader and the model are fakes."""
import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_drafter as td  # noqa: E402
import test_router as tr  # noqa: E402

from codetask import research as rs  # noqa: E402
from models.fake import StrictScriptedChatModel  # noqa: E402
from router import job as rj  # noqa: E402
from runner import load_config  # noqa: E402
from tools import web  # noqa: E402

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="the path jail needs openat; the VM runs these")

ROOT = Path(__file__).resolve().parent.parent
URL = "https://starlette.dev/middleware/"
PAGE = ("TrustedHostMiddleware\n\nEnforces that all incoming requests have a correctly set Host header, in order to "
        "guard against HTTP Host Header attacks.\n\nThe following arguments are supported:\n\n"
        "www_redirect - If set to True, requests to non-www versions of the allowed hosts will be redirected to their "
        "www counterparts. Defaults to True.\n\nIf an incoming request does not validate correctly then a 400 response "
        "will be sent.")
QUOTE = ("www_redirect - If set to True, requests to non-www versions of the allowed hosts will be redirected to "
         "their www counterparts. Defaults to True.")
ENV = "ledger_py312"
INSTALLED = rs.installed_packages(ENV)
STARLETTE = INSTALLED["starlette"][1]
ISSUE = "With allowed_hosts=['www.dashboard.example'], a request for dashboard.example gets 307, not 400 as documented."


class Spawn:
    """A fake downloader: PAGE for every allowlisted URL, counted."""

    def __init__(self, text=PAGE):
        self.calls, self.text = [], text

    def __call__(self, u, hosts, limits):
        self.calls.append(u)
        return {"ok": True, "url": u, "final_url": u, "chain": [u], "status": 200, "content_type": "text/html",
                "bytes": len(self.text), "ip": "104.21.0.1", "sha256": hashlib.sha256(self.text.encode()).hexdigest(),
                "text": self.text}


def handoff(**over):
    h = {"verdict": rs.SUPPORTED, "problem": "A non-www host next to a www name is redirected, not refused.",
         "api_behavior": "TrustedHostMiddleware redirects non-www hosts to www by default (www_redirect).",
         "dependency": {"package": "starlette", "version": STARLETTE},
         "sources": [{"url": URL, "quote": QUOTE}],
         "recommended_change": "Pass www_redirect=False to TrustedHostMiddleware in create_app.",
         "uncertainties": ["The page is not versioned; it is assumed to describe the installed release."]}
    h.update(over)
    return h


def call(name, args, id):
    return td.call(name, args, id)


READ = call("ReadDocs", {"url": URL}, "w1")
SUBMIT = call("SubmitHandoff", handoff(), "h1")


def cfg():
    c = load_config()
    c["roles"]["researcher"]["model"] = "fake:scripted"
    return c


def run(root, tmp_path, script, *, spawn=None, config=None, run_id="r", environment=ENV, max_usd=0.3, crash_at=None,
        resume=False, model=None):
    model = model or StrictScriptedChatModel(script=list(script))
    r = rs.run_research(run_id=run_id, runs_dir=tmp_path / "runs", cfg=config or cfg(), intake_name="shop",
                        issue=ISSUE, environment=environment, max_usd=max_usd, models={"researcher": model}, root=root,
                        web_spawn=spawn or Spawn(), crash_at=crash_at, resume=resume)
    return r, model, tmp_path / "runs" / run_id


def events(run_dir):
    return [json.loads(line) for line in (run_dir / "events.jsonl").read_text().splitlines() if line.strip()]


@pytest.fixture
def root(tmp_path):
    return td.make_root(tmp_path)


# ---- the gate (G1-G5), on a run directory with one stored page -----------------------------------------------------

@pytest.fixture
def stored(tmp_path):
    log = rs.EventLog(tmp_path / "e.jsonl")
    reader = web.DocsReader(load_config()["web"], tmp_path / "run", 1, log, spawn=Spawn())
    assert reader.read(URL, 1, "k")["ok"]
    return tmp_path / "run"


def check(run_dir, **over):
    return rs.gate(handoff(**over), installed=INSTALLED, run_dir=run_dir)


def test_a_handoff_whose_url_quote_and_version_hold_passes(stored):
    problems, h = check(stored)
    assert problems == [] and h["sources"][0]["sha256"] == hashlib.sha256(PAGE.encode()).hexdigest()


def test_a_quote_with_other_whitespace_passes(stored):
    assert check(stored, sources=[{"url": URL, "quote": QUOTE.replace(" ", "\n  ", 3)}])[0] == []


@pytest.mark.parametrize("url", [
    "https://starlette.dev/middleware",                # one character off: not the page that was read
    "https://starlette.dev/other/",                    # never read in this run
    "https://www.starlette.io/middleware/",            # named, not downloaded
])
def test_g1_a_url_not_downloaded_in_this_run_is_refused(stored, url):
    problems, h = check(stored, sources=[{"url": url, "quote": QUOTE}])
    assert h is None and any(p.startswith("G1") for p in problems)


def test_g1_a_refused_page_is_not_a_source(tmp_path):
    reader = web.DocsReader(load_config()["web"], tmp_path / "run", 1, rs.EventLog(tmp_path / "e.jsonl"),
                            spawn=lambda u, h, l: web.refusal("HTTP 404", [u], code="status"))
    assert not reader.read(URL, 1, "k")["ok"]
    problems, _ = check(tmp_path / "run")
    assert any(p.startswith("G1") for p in problems)


@pytest.mark.parametrize("quote", [
    QUOTE.replace("Defaults to True", "Defaults to False"),                       # one word changed
    "Enforces that all incoming requests will be redirected to their www counterparts",   # two places joined
    "requests to non-www hosts are always refused with a 400 response here",   # never on the page
])
def test_g2_a_quote_that_is_not_in_the_page_is_refused(stored, quote):
    problems, _ = check(stored, sources=[{"url": URL, "quote": quote}])
    assert any(p.startswith("G2") for p in problems)


@pytest.mark.parametrize("dep, ok", [
    ({"package": "starlette", "version": STARLETTE}, True),
    ({"package": "Starlette", "version": STARLETTE}, True),                      # PEP 503 names
    ({"package": "starlette", "version": "0.27.0"}, False),
    ({"package": "flask", "version": "3.0.0"}, False),
])
def test_g3_the_dependency_must_be_installed_at_that_version(stored, dep, ok):
    problems, _ = check(stored, dependency=dep)
    assert (problems == []) is ok and (ok or any(p.startswith("G3") for p in problems))


def test_g4_supported_needs_a_source_and_a_change(stored):
    assert check(stored, sources=[])[0]
    assert check(stored, recommended_change="")[0]
    assert check(stored, verdict="PROBABLY")[0]
    assert check(stored, sources=[{"url": URL, "quote": "short"}])[0]


def test_g5_insufficient_evidence_needs_an_uncertainty_and_may_have_no_source(stored):
    ok = dict(verdict=rs.INSUFFICIENT, sources=[], recommended_change="")
    assert check(stored, **ok)[0] == []
    assert check(stored, **ok, uncertainties=[])[0]
    assert any(p.startswith("G2") for p in check(stored, **{**ok, "sources": [{"url": URL, "quote": "x" * 30}]})[0])


# ---- the stage ------------------------------------------------------------------------------------------------------

def test_a_handoff_that_passes_ends_the_stage_and_is_written(root, tmp_path):
    r, model, d = run(root, tmp_path, [READ, SUBMIT])
    assert r["status"] == rs.RESEARCHED and r["verdict"] == rs.SUPPORTED and r["source_unchanged"]
    h = json.loads((d / "handoff.json").read_text())
    assert h["sources"][0]["quote"] == QUOTE and "Reviewed" not in (d / "HANDOFF.md").read_text()
    assert QUOTE in (d / "HANDOFF.md").read_text()
    prompt = model.calls[0]["messages"][1].content
    assert f"starlette=={STARLETTE}" in prompt and "starlette.dev" in prompt


def test_a_submit_before_reading_is_refused_by_g1_and_a_corrected_one_passes(root, tmp_path):
    r, model, d = run(root, tmp_path, [call("SubmitHandoff", handoff(), "h0"), READ, SUBMIT])
    assert r["status"] == rs.RESEARCHED
    assert any("G1" in m.content for m in model.calls[1]["messages"] if type(m).__name__ == "ToolMessage")


def test_submits_beyond_the_limit_end_without_a_handoff(root, tmp_path):
    bad = [call("SubmitHandoff", handoff(), f"h{i}") for i in range(3)]
    r, _, d = run(root, tmp_path, bad)
    assert r["status"] == rs.NO_HANDOFF and r["stop_reason"] == "submits_exhausted" and not (d / "handoff.json").exists()


def test_insufficient_evidence_is_an_outcome(root, tmp_path):
    sub = call("SubmitHandoff", handoff(verdict=rs.INSUFFICIENT, sources=[], recommended_change=""), "h1")
    r, _, d = run(root, tmp_path, [READ, sub])
    assert r["status"] == rs.INCONCLUSIVE and json.loads((d / "handoff.json").read_text())["verdict"] == rs.INSUFFICIENT


@pytest.mark.parametrize("name, args", [
    ("WriteFile", {"path": "src/shop.py", "content": "x = 1\n"}),
    ("EditFile", {"path": "src/shop.py", "old_text": "def", "new_text": "xx"}),
    ("RunValidation", {"id": "v1"}),
])
def test_tools_that_write_or_run_are_neither_offered_nor_run(root, tmp_path, name, args):
    config = cfg()
    config["tools"]["researcher"] = ["list_files", "read_file", "read_docs", "write_file", "edit_file", "run_validation"]
    r, model, d = run(root, tmp_path, [call(name, args, "x1"), READ, SUBMIT], config=config)
    offered = {t.__name__ for t in model.bound_tools}             # bound for every step (none is a final step)
    assert name not in offered and "ReadDocs" in offered
    assert r["status"] == rs.RESEARCHED and (d / "source" / "src" / "shop.py").read_text() == td.BUGGY
    seen = [m.content for m in model.calls[1]["messages"] if type(m).__name__ == "ToolMessage"]
    assert seen and seen[-1].startswith("Denied")


def test_a_changed_source_blocks_the_stage(root, tmp_path, monkeypatch):
    real = rs.Toolbox.run

    def tamper(self, c, step_key=None):
        (Path(self.workspace) / "src" / "shop.py").write_text("changed\n")
        return real(self, c, step_key)
    monkeypatch.setattr(rs.Toolbox, "run", tamper)
    r, _, _ = run(root, tmp_path, [READ, SUBMIT])
    assert r["status"] == rs.BLOCKED and r["blocked_reason"] == "source_changed"


def test_an_environment_off_the_web_list_or_without_pins_is_blocked(root, tmp_path):
    r, model, _ = run(root, tmp_path, [SUBMIT], environment="sympy_py39")
    assert r["status"] == rs.BLOCKED and model.calls == []
    config = cfg()
    config["web"]["environments"] = ["argus"]
    r, model, _ = run(root, tmp_path, [SUBMIT], environment="argus", config=config, run_id="r2")
    assert r["status"] == rs.BLOCKED and "requirements" in r["stop_reason"] and model.calls == []


def test_the_quote_gate_reads_the_page_stored_by_this_run_not_a_new_download(root, tmp_path):
    spawn = Spawn()
    r, _, d = run(root, tmp_path, [READ, call("ReadDocs", {"url": URL, "part": 1}, "w2"), SUBMIT], spawn=spawn)
    assert r["status"] == rs.RESEARCHED and spawn.calls == [URL]


# ---- crash-resume across processes -------------------------------------------------------------------------------

PROC = ("import sys; sys.path[:0] = [sys.argv[1], sys.argv[1] + '/tests']; import test_research as t; "
        "sys.exit(t._proc(*sys.argv[2:]))")


def _proc(root, runs, crash_at, resume, spawned):
    def spawn(u, h, l):
        with open(spawned, "a") as f:
            f.write(u + "\n")
        return Spawn()(u, h, l)
    r = rs.run_research(run_id="rc", runs_dir=runs, cfg=cfg(), intake_name="shop", issue=ISSUE, environment=ENV,
                        max_usd=0.3, resume=resume == "1", crash_at=None if crash_at == "-" else crash_at, root=root,
                        web_spawn=spawn)
    return 0 if r["status"] == rs.RESEARCHED else 1


def _script(name, args, id):
    return {"tool_calls": [{"name": name, "args": args, "id": id}], "usage": {"input_tokens": 500, "output_tokens": 60}}


def _spawn(tmp_path, root, crash_at, resume):
    env = {**os.environ, "ARGUS_FAKE_SCRIPT": str(tmp_path / "script.json")}
    return subprocess.run([sys.executable, "-c", PROC, str(ROOT), str(root), str(tmp_path / "runs"), crash_at, resume,
                           str(tmp_path / "spawned.log")], cwd=ROOT, capture_output=True, text=True, env=env,
                          timeout=300)


@pytest.mark.parametrize("point, model_calls", [
    ("setup@after_copy", 2),
    ("research@after_llm", 3),                    # step 0 was not committed: it is bought again (the spare ReadDocs)
    ("research@after_tool:ReadDocs", 2),
    ("research@after_tool:SubmitHandoff", 2),
    ("finalize@after_write", 2),
])
def test_a_crash_anywhere_resumes_without_buying_or_downloading_again(root, tmp_path, point, model_calls):
    read = _script("ReadDocs", {"url": URL}, "w1")
    script = [read, *([read] if point == "research@after_llm" else []), _script("SubmitHandoff", handoff(), "h1")]
    (tmp_path / "script.json").write_text(json.dumps(script))
    r1 = _spawn(tmp_path, root, point, "0")
    assert r1.returncode == 42, (r1.stdout[-2000:], r1.stderr[-2000:])
    r2 = _spawn(tmp_path, root, "-", "1")
    assert r2.returncode == 0, (r2.stdout[-2000:], r2.stderr[-2000:])
    d = tmp_path / "runs" / "rc"
    assert json.loads((d / "result.json").read_text())["status"] == rs.RESEARCHED and (d / "handoff.json").exists()
    evs = events(d)
    i = next(n for n, e in enumerate(evs) if e["event"] == "crash_simulated")
    before, after = evs[:i], evs[i:]
    llm = {e["step"] for e in before if e["event"] == "step_committed" and e["kind"] == "llm"}
    assert not llm & {e["step"] for e in after if e["event"] == "llm_call" and e.get("status") == "ok"}
    tools = {(e["step"], e["tool"]) for e in before if e["event"] == "step_committed" and e["kind"] == "tool"}
    assert not tools & {(e["step"], e["tool"]) for e in after if e["event"] == "step_committed" and e["kind"] == "tool"}
    assert len([e for e in evs if e["event"] == "llm_call" and e.get("status") == "ok"]) == model_calls
    spawned = (tmp_path / "spawned.log").read_text().splitlines() if (tmp_path / "spawned.log").exists() else []
    assert len(spawned) <= 1                       # the page is kept by the run: never downloaded twice


# ---- the router ---------------------------------------------------------------------------------------------------

def router_cfg():
    c = tr.cfg()
    c["roles"]["researcher"]["model"] = "fake:scripted"
    return c


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(rj, "environment_pin", lambda cfg, name, root=None: ("sha256:" + "0" * 64, None))
    monkeypatch.setattr(rj, "environment_changed", lambda job, cfg: None)
    monkeypatch.setattr(rj, "_check_environment", lambda job, cfg: None)
    e = tr.Env(tmp_path, config=router_cfg())
    e.researcher = StrictScriptedChatModel(script=[READ, SUBMIT])
    e.deps.models["researcher"] = e.researcher
    e.deps.web_spawn = Spawn()
    return e


def research(e, **kw):
    return e.code(environment=ENV, research=True, **kw)


def handoff_sha(e):
    job = rj.open_job("jtest", e.jobs)
    return hashlib.sha256(rj.handoff_path(job).read_bytes()).hexdigest()


def test_code_with_research_runs_r1_and_waits_for_the_review(env):
    job = research(env)
    assert job.data["state"] == rj.AWAITING_RESEARCH_REVIEW and "d1" not in job.data["stages"]
    assert env.drafter.calls == [] and "network: ReadDocs" in env.confirms[0] and "read-only" in env.confirms[0]
    text = rj.status("jtest", jobs_dir=env.jobs)
    assert f"argus research-ok jtest --sha {handoff_sha(env)[:12]}" in text
    assert rj.spent_nano(rj.open_job("jtest", env.jobs)) > 0


def test_research_ok_starts_the_drafter_with_the_handoff_in_its_issue(env):
    research(env)
    job, r = rj.research_ok("jtest", sha=handoff_sha(env)[:12], cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs)
    assert job.data["state"] == rj.AWAITING_APPROVAL
    content = env.drafter.calls[0]["messages"][1].content
    prompt = content if isinstance(content, str) else "".join(b["text"] for b in content)
    assert rj.HANDOFF_LABEL in prompt and QUOTE in prompt and td.ISSUE in prompt
    assert rj.job_issue(job).startswith(td.ISSUE) and QUOTE in rj.job_issue(job)


@pytest.mark.parametrize("bad", ["", "0" * 12, "abc"])
def test_research_ok_needs_the_sha_status_shows(env, bad):
    research(env)
    with pytest.raises(rj.Refused):
        rj.research_ok("jtest", sha=bad, cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs)
    assert env.drafter.calls == []


def test_a_handoff_changed_after_it_was_written_is_not_accepted(env):
    research(env)
    sha = handoff_sha(env)
    path = rj.handoff_path(rj.open_job("jtest", env.jobs))
    h = json.loads(path.read_text())
    h["recommended_change"] = "Rewrite the host check by hand."
    path.write_text(json.dumps(h, indent=2) + "\n")
    with pytest.raises(rj.Refused, match="not the one the research stage wrote"):
        rj.research_ok("jtest", sha=sha[:12], cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs)
    assert env.drafter.calls == []


def test_an_inconclusive_research_stops_the_job_without_more_spending(env):
    env.researcher.script[:] = [READ, call("SubmitHandoff", handoff(verdict=rs.INSUFFICIENT, sources=[],
                                                                    recommended_change=""), "h1")]
    job = research(env)
    assert job.data["state"] == rj.RESEARCH_INCONCLUSIVE
    with pytest.raises(rj.Refused):
        rj.research_ok("jtest", sha=handoff_sha(env)[:12], cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs)
    assert env.drafter.calls == [] and "did not settle it" in rj.status("jtest", jobs_dir=env.jobs)


def test_research_needs_an_environment_on_the_web_list_before_a_job_is_made(env):
    for kw in ({}, {"environment": "sympy_py39"}):
        with pytest.raises(rj.Refused, match="--research needs --environment"):
            env.code(research=True, **kw)
        assert not (env.jobs / "jtest").exists()


def test_without_research_there_is_no_r1_and_the_drafter_runs(env):
    job = env.code(environment=ENV)
    assert "r1" not in job.data["stages"] and env.researcher.calls == [] and env.drafter.calls


def test_a_handoff_too_long_for_the_issue_is_refused(env, monkeypatch):
    research(env)
    monkeypatch.setattr(rs, "MAX_ISSUE", len(ISSUE) + 10)
    with pytest.raises(rj.Refused, match="more than"):
        rj.research_ok("jtest", sha=handoff_sha(env)[:12], cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs)


def test_the_approved_contract_carries_the_reviewed_handoff(env):
    research(env)
    rj.research_ok("jtest", sha=handoff_sha(env)[:12], cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs)
    job, _ = env.approve()
    contract = json.loads((job.root / "fixtures" / "contracts" / f"{job.data['approval']['task']}.json").read_text())
    assert rj.HANDOFF_LABEL in contract["inputs"]["issue"] and QUOTE in contract["inputs"]["issue"]


# ---- mutation-check additions -------------------------------------------------------------------------------------

def test_g1_a_stored_refusal_with_text_is_not_a_source(tmp_path):
    path = web.page_path(tmp_path / "run", URL)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"ok": False, "reason": "HTTP 404", "text": PAGE}))
    assert any(p.startswith("G1") for p in check(tmp_path / "run")[0])


def test_g2_whitespace_of_the_page_is_normalized_too(tmp_path):
    reader = web.DocsReader(load_config()["web"], tmp_path / "run", 1, rs.EventLog(tmp_path / "e.jsonl"),
                            spawn=Spawn(text=PAGE.replace("redirected to their", "redirected\n   to their")))
    assert reader.read(URL, 1, "k")["ok"]
    assert check(tmp_path / "run")[0] == []


@pytest.mark.parametrize("quote", ["Defaults to True.", "x" * 601])
def test_g4_a_quote_must_have_20_to_600_characters_even_when_it_is_on_the_page(tmp_path, quote):
    text = PAGE + " " + "x" * 601
    reader = web.DocsReader(load_config()["web"], tmp_path / "run", 1, rs.EventLog(tmp_path / "e.jsonl"),
                            spawn=Spawn(text=text))
    assert reader.read(URL, 1, "k")["ok"]
    problems, _ = check(tmp_path / "run", sources=[{"url": URL, "quote": quote}])
    assert problems and all(not p.startswith("G2") for p in problems)


def test_submithandoff_with_another_call_runs_nothing(root, tmp_path):
    both = td.reply(tool_calls=[{"name": "ReadDocs", "args": {"url": URL}, "id": "w0"},
                                {"name": "SubmitHandoff", "args": handoff(), "id": "h0"}])
    spawn = Spawn()
    r, model, d = run(root, tmp_path, [both, READ, SUBMIT], spawn=spawn)
    first = [m.content for m in model.calls[1]["messages"] if type(m).__name__ == "ToolMessage"]
    assert all(t.startswith("Rejected: SubmitHandoff must be the only tool call") for t in first) and len(first) == 2
    assert r["status"] == rs.RESEARCHED and r["research"]["submits"] == 1 and spawn.calls == [URL]


def test_the_last_steps_offer_only_submithandoff_and_refuse_any_other(root, tmp_path, monkeypatch):
    offered = []
    real = StrictScriptedChatModel.bind_tools

    def recording(self, tools, tool_choice=None, **kw):
        offered.append(sorted(t.__name__ for t in tools))
        return real(self, tools, tool_choice=tool_choice, **kw)
    monkeypatch.setattr(StrictScriptedChatModel, "bind_tools", recording)
    config = cfg()
    config["research"]["max_steps"] = 7
    reads = [call("ReadDocs", {"url": URL}, f"w{i}") for i in range(5)]           # steps 0-4; 4 is final
    r, model, d = run(root, tmp_path, reads + [SUBMIT], config=config)
    assert rs.final_from(7) == 4 and offered[3] == ["ListFiles", "ReadDocs", "ReadFile", "SearchFiles", "SubmitHandoff"]
    assert offered[4] == offered[5] == ["SubmitHandoff"]
    seen = [m.content for m in model.calls[5]["messages"] if type(m).__name__ == "ToolMessage"]
    assert seen[-1].startswith("Refused: ReadDocs is not offered in the last 3 steps")
    assert r["status"] == rs.RESEARCHED


def test_a_committed_submit_is_not_gated_again_on_resume(root, tmp_path):
    """A rejected submit at step 0 was committed; a crash at step 1 replays it from the memo, never gates it again."""
    script = [_script("SubmitHandoff", handoff(), "h0"), _script("ReadDocs", {"url": URL}, "w1"),
              _script("SubmitHandoff", handoff(), "h1")]
    (tmp_path / "script.json").write_text(json.dumps(script))
    assert _spawn(tmp_path, root, "research@after_tool:ReadDocs", "0").returncode == 42
    assert _spawn(tmp_path, root, "-", "1").returncode == 0
    evs = events(tmp_path / "runs" / "rc")
    assert [e["ok"] for e in evs if e["event"] == "handoff_checked"] == [False, True]
    # gated again, the step-0 submit would pass now (the page is stored) and end the stage a step early
    assert [e["steps"] for e in evs if e["event"] == "research_end"] == [2]


def test_research_ok_is_refused_unless_the_job_awaits_the_research_review(env):
    env.researcher.script[:] = [READ, call("SubmitHandoff", handoff(verdict=rs.INSUFFICIENT, sources=[],
                                                                    recommended_change=""), "h1")]
    research(env)
    with pytest.raises(rj.Refused, match="not AWAITING_RESEARCH_REVIEW"):
        rj.research_ok("jtest", sha=handoff_sha(env)[:12], cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs)
