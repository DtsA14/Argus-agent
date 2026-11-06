"""SPEC_JUDGE: the judge j1 of a code job (codetask/judge.py, router/job.py `judge`); not the rubric judge of
tests/test_judge.py. The model is a fake; the money goes through the real LLMCaller ledger. A finished job is written by
hand: a draft stage, an agent stage with a valid review package."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_drafter as td  # noqa: E402
import test_research_job as t  # noqa: E402
from codetask import judge as jd  # noqa: E402
from harness.events import EventLog  # noqa: E402
from harness.llm import reconcile_ledger  # noqa: E402
from models.fake import StrictScriptedChatModel  # noqa: E402
from router import job as rj  # noqa: E402
from runner import load_config  # noqa: E402

ROOT = t.ROOT
ISSUE = "Show the jobs' total cost under the table."
PATCH = ("diff --git a/src/App.jsx b/src/App.jsx\n--- a/src/App.jsx\n+++ b/src/App.jsx\n@@ -1 +1 @@\n-old\n+new\n"
         "diff --git a/src/total.test.jsx b/src/total.test.jsx\nnew file mode 100644\n")
DRAFT = {"draft_version": 1, "base": "base", "plan": {"files": ["src/App.jsx"], "steps": ["add the total"], "risks": []},
         "contract": {"scope": {"writable": ["src/App.jsx"], "protected": []}, "validation": [], "tools": []},
         "new_tests": [{"path": "src/total.test.jsx", "content": "test('total', () => {})"}],
         "unverifiable": ["no float rounding is checked"]}
SECRET = "THE-HUMAN-REJECTED-THIS-BECAUSE"
BLOCKED = {"verdict": "BLOCK", "findings": [{"where": "src/App.jsx:1", "problem": "The total is hard-coded."}],
           "summary": "The patch fakes the total."}
PASSED = {"verdict": "PASS", "findings": [], "summary": "The patch adds the total as asked."}


def cfg():
    c = load_config()
    c["roles"]["code_judge"]["model"] = "fake:scripted"
    return c


def make_job(jobs, state=rj.REVIEW_READY, max_usd=1.0, job_id="jj"):
    d = jobs / job_id
    review = d / "runs" / f"{job_id}-a1" / "review"
    review.mkdir(parents=True)
    (review / "changes.patch").write_text(PATCH)
    (review / "tests.md").write_text("| validation:total | pass | pass |\n")
    (review / "claims.md").write_text("The agent says the total is shown.\n")
    (review / "PR.md").write_text(f"PR {SECRET}-pr\n")
    (review / "provenance.json").write_text(json.dumps({"note": f"{SECRET}-prov"}))
    draft_dir = d / "runs" / f"{job_id}-d1"
    draft_dir.mkdir(parents=True)
    (draft_dir / "draft.json").write_text(json.dumps(DRAFT))
    sha = rj.draft_sha(draft_dir / "draft.json")
    data = {"job": job_id, "kind": "code", "state": state, "created_at": "2026-11-05T00:00:00Z", "max_usd": max_usd,
            "inputs": {"repo": str(jobs / "repo"), "commit": "abc", "issue": ISSUE},
            "stages": {"d1": {"kind": "draft", "run_id": f"{job_id}-d1", "cap_usd": 0.7, "status": "DRAFTED",
                              "usd": 0.0, "draft_sha256": sha},
                       "a1": {"kind": "agent", "run_id": f"{job_id}-a1", "cap_usd": 0.5, "status": "DONE", "usd": 0.0,
                              "review": {"valid": True, "problems": [], "dir": str(review)}}},
            "approval": {"draft_sha256": sha, "task": "task"}, "intake": {"commit": "abc"},
            "log": [{"at": "2026-11-05T00:00:00Z", "what": "state", "old": "REVIEW_READY", "new": state,
                     "reason": f"{SECRET}-reason"}]}
    (d / "job.json").write_text(json.dumps(data))
    return rj.open_job(job_id, jobs)


class Env:
    def __init__(self, tmp_path, script, **kw):
        self.jobs, self.said, self.confirms = tmp_path / "jobs", [], []
        self.model = StrictScriptedChatModel(script=list(script))
        self.cfg = cfg()
        self.deps = rj.Deps(confirm=lambda text: self.confirms.append(text) or True, get_key=lambda: "unused",
                            isatty=lambda: True, models={"code_judge": self.model}, clock=lambda: "2026-11-05T00:00:00Z",
                            echo=self.said.append)
        self.job0 = make_job(self.jobs, **kw)

    def judge(self):
        return rj.judge("jj", cfg=self.cfg, deps=self.deps, jobs_dir=self.jobs)

    def job(self):
        return rj.open_job("jj", self.jobs)


def submit(args, id="j"):
    return td.call("SubmitJudgement", args, id)


def ledger_calls(job, sid="j1"):
    return reconcile_ledger(EventLog(job.runs / job.data["stages"][sid]["run_id"] / "events.jsonl").read())[1]["calls"]


# ---- G1: only a finished job with a valid package ------------------------------------------------------------------

@pytest.mark.parametrize("state", [rj.AWAITING_APPROVAL, rj.AGENT_FAILED, rj.REVIEW_INVALID, rj.ABANDONED])
def test_a_job_that_is_not_finished_is_not_judged(tmp_path, state):
    env = Env(tmp_path, [submit(PASSED)], state=state)
    with pytest.raises(rj.Refused, match="nothing was judged"):
        env.judge()
    assert "j1" not in env.job().data["stages"] and env.model.calls == [] and env.confirms == []


@pytest.mark.parametrize("state", [rj.REVIEW_READY, rj.APPLIED, rj.REJECTED])
def test_a_finished_job_is_judged(tmp_path, state):
    env = Env(tmp_path, [submit(BLOCKED)], state=state)
    job, r = env.judge()
    assert r["status"] == jd.JUDGED and r["judgement"]["verdict"] == "BLOCK"
    st = job.data["stages"]["j1"]
    assert st["status"] == jd.JUDGED and st["verdict"] == "BLOCK" and st["findings"] == 1 and st["usd"] > 0
    md = (job.dir / "JUDGE-j1.md").read_text()
    assert "**Verdict**: BLOCK" in md and "`src/App.jsx:1`: The total is hard-coded." in md
    assert len(env.confirms) == 1 and "data sent out" in env.confirms[0] and "advisory only" in env.confirms[0]


@pytest.mark.parametrize("change", ["invalid", "not_done", "no_review"])
def test_a_job_without_a_valid_package_is_not_judged(tmp_path, change):
    env = Env(tmp_path, [submit(PASSED)])
    job = env.job()
    a1 = job.data["stages"]["a1"]
    if change == "invalid":
        a1["review"]["valid"] = False
    elif change == "not_done":
        a1["status"] = "FAILED"
    else:
        del a1["review"]
    job.save()
    with pytest.raises(rj.Refused, match="no valid review package"):
        env.judge()
    assert env.model.calls == [] and "j1" not in env.job().data["stages"]


# ---- G2, G3: what the model sees, and nothing when it is too large ----------------------------------------------

def test_the_prompt_has_the_issue_draft_and_package_and_nothing_else(tmp_path):
    env = Env(tmp_path, [submit(PASSED)])
    env.judge()
    prompt = "\n".join(m.content if isinstance(m.content, str) else "".join(b.get("text", "") for b in m.content)
                       for m in env.model.calls[0]["messages"])
    for text in (ISSUE, "add the total", "test('total', () => {})", "no float rounding is checked", "+new",
                 "validation:total", "The agent says the total is shown."):
        assert text in prompt, text
    assert SECRET not in prompt                 # job.json's reasons, PR.md, provenance.json
    assert [x.__name__ for x in env.model.bound_tools] == ["SubmitJudgement"]


def test_an_input_too_large_ends_not_judged_before_any_request(tmp_path):
    env = Env(tmp_path, [submit(PASSED)])
    env.cfg["code_judge"]["max_input_chars"] = 200
    job, r = env.judge()
    assert r["status"] == jd.NOT_JUDGED and "input too large" in r["stop_reason"] and env.model.calls == []
    assert ledger_calls(job) == 0 and job.data["stages"]["j1"]["status"] == jd.NOT_JUDGED


# ---- G4: the gate ---------------------------------------------------------------------------------------------------

PATHS = jd.nameable(PATCH, DRAFT)


def test_a_block_needs_a_finding():
    problems, _ = jd.judge_gate({**BLOCKED, "findings": []}, PATHS)
    assert any("needs at least one finding" in p for p in problems)


@pytest.mark.parametrize("where", ["README.md", "src/other.jsx:3", "", "src/App.jsx.bak"])
def test_a_finding_must_name_a_file_of_the_patch_or_the_draft(where):
    problems, _ = jd.judge_gate({**BLOCKED, "findings": [{"where": where, "problem": "x"}]}, PATHS)
    assert problems


@pytest.mark.parametrize("where", ["src/App.jsx", "src/App.jsx:12", "src/App.jsx:3-9", "src/total.test.jsx::total",
                                   " src/total.test.jsx :: the total row"])
def test_a_finding_naming_a_patch_or_draft_file_passes(where):
    problems, j = jd.judge_gate({**BLOCKED, "findings": [{"where": where, "problem": "wrong"}]}, PATHS)
    assert problems == [] and j["verdict"] == "BLOCK"


def test_text_over_its_limit_is_refused_and_cut_only_on_the_last_submit():
    long = {**BLOCKED, "summary": "word " * (jd.SUMMARY_MAX // 4), "findings": [{"where": "src/App.jsx",
                                                                   "problem": "bad " * (jd.PROBLEM_MAX // 3)}]}
    assert len(jd.judge_gate(long, PATHS)[0]) == 2
    problems, j = jd.judge_gate(long, PATHS, last=True)
    assert problems == [] and len(j["summary"]) <= jd.SUMMARY_MAX and j["summary"].endswith("…")
    assert len(j["findings"][0]["problem"]) <= jd.PROBLEM_MAX


@pytest.mark.parametrize("verdict", ["APPROVE", "block", None])
def test_only_pass_or_block(verdict):
    assert jd.judge_gate({**PASSED, "verdict": verdict}, PATHS)[0]


def test_a_rejected_submit_is_told_why_and_the_next_one_counts(tmp_path):
    bad = {**BLOCKED, "findings": [{"where": "README.md", "problem": "x"}]}
    env = Env(tmp_path, [submit(bad, "a"), submit(BLOCKED, "b")])
    job, r = env.judge()
    assert r["status"] == jd.JUDGED and job.data["stages"]["j1"]["findings"] == 1
    answers = [str(m.content) for m in env.model.calls[1]["messages"] if type(m).__name__ == "ToolMessage"]
    assert any("neither a file of the patch" in a for a in answers)


# ---- G5: advice only -----------------------------------------------------------------------------------------------

def _shape(job):
    d = dict(job.data)
    return d["state"], d["approval"], {k: v for k, v in d["stages"].items() if v["kind"] != "judge"}


def test_judging_changes_nothing_approve_applied_or_reject_use(tmp_path):
    env = Env(tmp_path, [submit(BLOCKED)])
    before = _shape(env.job())
    job, _ = env.judge()
    assert _shape(job) == before
    rj.reject("jj", "not applied", deps=env.deps, jobs_dir=env.jobs)           # still possible after a BLOCK
    assert env.job().data["state"] == rj.REJECTED


def test_status_shows_the_verdict(tmp_path):
    env = Env(tmp_path, [submit(BLOCKED)])
    env.judge()
    text = rj.status("jj", jobs_dir=env.jobs)
    assert "judge j1: BLOCK (1 finding(s))" in text and "STALE" not in text and "JUDGE-j1.md" in text


# ---- G6, G9: never bought twice for one package; a new package is judged again ------------------------------------

def test_a_judged_package_is_shown_and_never_judged_again(tmp_path):
    env = Env(tmp_path, [submit(BLOCKED)])
    job, _ = env.judge()
    spent = rj.spent_nano(job)
    job, r = env.judge()
    assert r["verdict"] == "BLOCK" and len(env.model.calls) == 1 and rj.spent_nano(job) == spent
    assert list(rj.judge_stages(job)) == ["j1"] and len(env.confirms) == 1
    assert any("already judged" in s for s in env.said)


def test_a_changed_package_is_stale_and_judged_in_a_new_stage(tmp_path):
    env = Env(tmp_path, [submit(BLOCKED), submit(PASSED, "k")])
    job, _ = env.judge()
    (Path(job.data["stages"]["a1"]["review"]["dir"]) / "changes.patch").write_text(PATCH + "\n")
    assert "STALE" in rj.status("jj", jobs_dir=env.jobs)
    job, r = env.judge()
    assert rj.judge_stages(job) == ["j1", "j2"] and r["judgement"]["verdict"] == "PASS"
    assert job.data["stages"]["j1"]["verdict"] == "BLOCK" and ledger_calls(job, "j1") == 1
    assert "BLOCK" in (job.dir / "JUDGE-j1.md").read_text() and "PASS" in (job.dir / "JUDGE-j2.md").read_text()


def test_a_not_judged_stage_can_be_run_again_in_a_new_stage(tmp_path):
    env = Env(tmp_path, [submit(PASSED)])
    env.cfg["code_judge"]["max_input_chars"] = 200
    env.judge()
    env.cfg["code_judge"]["max_input_chars"] = 120000
    job, r = env.judge()
    assert rj.judge_stages(job) == ["j1", "j2"] and r["status"] == jd.JUDGED


# ---- G8: money --------------------------------------------------------------------------------------------------------

def test_too_little_left_is_refused_before_sending_and_the_job_is_not_blocked(tmp_path):
    env = Env(tmp_path, [submit(PASSED)], max_usd=0.01)
    with pytest.raises(rj.Refused, match="left for the judge"):
        env.judge()
    job = env.job()
    assert job.data["state"] == rj.REVIEW_READY and "j1" not in job.data["stages"] and env.model.calls == []
    assert env.confirms == []


def test_the_stage_cap_is_the_smaller_of_judge_max_usd_and_what_is_left(tmp_path):
    env = Env(tmp_path, [submit(PASSED)], max_usd=0.5)
    job, _ = env.judge()
    assert job.data["stages"]["j1"]["cap_usd"] == 0.10
    env2 = Env(tmp_path / "b", [submit(PASSED)])
    env2.cfg["router"]["judge_max_usd"] = 0.07
    env2.cfg["code_judge"]["cap_usd"] = 0.05
    job, _ = env2.judge()
    assert job.data["stages"]["j1"]["cap_usd"] == 0.07


# ---- G7: crash-resume --------------------------------------------------------------------------------------------------

PROC = ("import sys; sys.path[:0] = [sys.argv[1], sys.argv[1] + '/tests']; import test_code_judge as t; "
        "sys.exit(t._proc(*sys.argv[2:]))")


def _proc(jobs, crash_at):
    from codetask import judge as j
    real = j.run_judge
    if crash_at not in ("-", "resume"):
        j.run_judge = lambda **kw: real(**kw, crash_at=crash_at)
    deps = rj.Deps(confirm=lambda text: True, get_key=lambda: "unused", isatty=lambda: True,
                   clock=lambda: "2026-11-05T00:00:00Z", echo=lambda s: None)
    if crash_at == "resume":
        _, r = rj.resume("jj", cfg=cfg(), deps=deps, jobs_dir=jobs)
    else:
        _, r = rj.judge("jj", cfg=cfg(), deps=deps, jobs_dir=jobs)
    return 0 if r["status"] == j.JUDGED else 1


@pytest.mark.parametrize("point, again", [("judge@after_llm", "-"), ("judge@after_tool:SubmitJudgement", "-"),
                                          ("work@after_commit", "-"), ("judge@after_llm", "resume")])
def test_a_crashed_judge_continues_without_buying_again(tmp_path, point, again):
    reply = t._script("SubmitJudgement", BLOCKED, "j")
    script = [reply, reply] if point.endswith("after_llm") else [reply]    # an uncommitted reply is bought again
    (tmp_path / "script.json").write_text(json.dumps(script))
    make_job(tmp_path / "jobs")
    env = {**os.environ, "ARGUS_FAKE_SCRIPT": str(tmp_path / "script.json")}

    def go(arg):
        return subprocess.run([sys.executable, "-c", PROC, str(ROOT), str(tmp_path / "jobs"), arg], cwd=ROOT,
                              capture_output=True, text=True, env=env, timeout=300)
    r1 = go(point)
    assert r1.returncode == 42, (r1.stdout[-2000:], r1.stderr[-2000:])
    job = rj.open_job("jj", tmp_path / "jobs")
    assert job.data["stages"]["j1"].get("status") is None
    r2 = go(again)
    assert r2.returncode == 0, (r2.stdout[-2000:], r2.stderr[-2000:])
    job = rj.open_job("jj", tmp_path / "jobs")
    assert rj.judge_stages(job) == ["j1"] and job.data["stages"]["j1"]["verdict"] == "BLOCK"
    evs = EventLog(job.runs / "jj-j1" / "events.jsonl").read()
    i = next(n for n, e in enumerate(evs) if e["event"] == "crash_simulated")
    committed = {e["step"] for e in evs[:i] if e["event"] == "step_committed" and e["kind"] == "llm"}
    rebought = {e["step"] for e in evs[i:] if e["event"] == "llm_call" and e.get("status") == "ok"}
    assert not committed & rebought
    _, totals = reconcile_ledger(evs)
    assert totals["unknown_after_crash"] == 0 and totals["calls"] == len(script)


# ---- G10: the gateway pin --------------------------------------------------------------------------------------------

def test_the_judge_model_is_pinned_to_its_upstreams_with_no_other_provider():
    from models import gateway
    from models.registry import ModelRef
    c = load_config()
    ref = ModelRef.parse(c["roles"]["code_judge"]["model"])
    assert gateway.is_gateway(c, ref) and gateway.entry(c, ref) == {"upstream": ["baidu/fp8", "novita/fp8"],
                                                                     "free": False}
    p = gateway.request_params(c, ref, {})["extra_body"]["provider"]
    assert p["order"] == p["only"] == ["baidu/fp8", "novita/fp8"] and p["allow_fallbacks"] is False
    assert gateway.fallback_chain(c, "code_judge") == [str(ref)]
    gateway.check_use(c, "code_judge", ref)                       # a paid model: no free-role rule applies
    assert c["prices"][str(ref)]["input"] > 0


# ---- review findings (code review medium, 2026-11-05) ----------------------------------------------------------------

def test_a_copied_job_is_judged_on_its_own_package_not_the_recorded_dir(tmp_path):
    env = Env(tmp_path, [submit(PASSED)])
    job = env.job()
    elsewhere = tmp_path / "original" / "review"
    elsewhere.mkdir(parents=True)
    for name in jd.PACKAGE:
        (elsewhere / name).write_text(f"{SECRET}-original {name}")
    job.data["stages"]["a1"]["review"]["dir"] = str(elsewhere)          # where the job ran before it was copied
    job.save()
    env.judge()
    prompt = "".join(b.get("text", "") if isinstance(b, dict) else str(b)
                     for m in env.model.calls[0]["messages"] for b in (m.content if isinstance(m.content, list)
                                                                       else [m.content]))
    assert "+new" in prompt and SECRET not in prompt


def test_the_judge_file_is_written_before_the_stage_is_judged_and_rebuilt_when_missing(tmp_path, monkeypatch):
    env = Env(tmp_path, [submit(BLOCKED)])
    real = rj._write_judge_file

    def dies(*a, **kw):
        raise OSError("disk full")
    monkeypatch.setattr(rj, "_write_judge_file", dies)
    with pytest.raises(OSError):
        env.judge()
    assert env.job().data["stages"]["j1"].get("status") is None       # never JUDGED without its file
    monkeypatch.setattr(rj, "_write_judge_file", real)
    job, r = env.judge()                                                # continued from the committed result
    assert r["status"] == jd.JUDGED and len(env.model.calls) == 1 and ledger_calls(job) == 1
    judge_md = job.dir / "JUDGE-j1.md"
    judge_md.unlink()
    env.judge()
    assert "**Verdict**: BLOCK" in judge_md.read_text() and len(env.model.calls) == 1
    assert "pinned to" not in judge_md.read_text() or "baidu/fp8" in judge_md.read_text()


def test_the_judge_file_names_the_provider_pin(tmp_path):
    env = Env(tmp_path, [submit(PASSED)])
    env.cfg["gateway_models"]["fake:scripted"] = {"upstream": ["somewhere/fp8"]}
    job, _ = env.judge()
    assert "fake:scripted (pinned to somewhere/fp8)" in (job.dir / "JUDGE-j1.md").read_text()


def test_resume_continues_a_cut_off_judge_but_never_starts_one_on_another_package(tmp_path):
    env = Env(tmp_path, [submit(PASSED)], state=rj.APPLIED)
    job = env.job()
    job.data["stages"]["j1"] = {"kind": "judge", "run_id": "jj-j1", "cap_usd": 0.1, "started_at": "x",
                                "package": {"changes.patch": "0" * 64}, "draft_sha256": "y"}
    job.save()
    assert "cut off before it ended" in rj.status("jj", jobs_dir=env.jobs)
    with pytest.raises(rj.Refused, match="for another review package"):
        rj.resume("jj", cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs)
    assert env.model.calls == [] and rj.judge_stages(env.job()) == ["j1"]


@pytest.mark.parametrize("patch, path", [
    ('diff --git "a/my page.html" "b/my page.html"\n--- "a/my page.html"\n+++ "b/my page.html"\n', "my page.html"),
    ('diff --git "a/caf\\303\\251.txt" "b/caf\\303\\251.txt"\n--- /dev/null\n+++ "b/caf\\303\\251.txt"\n', "café.txt"),
    ("diff --git a/x.txt b/x.txt\r\n--- a/x.txt\r\n+++ b/x.txt\r\n", "x.txt"),
    ("diff --git a/old b/x b/y\nrename from old b/x\nrename to y\n", "old b/x"),
    ("diff --git a/logo.png b/logo.png\nnew file mode 100644\nGIT binary patch\n", "logo.png"),
])
def test_every_kind_of_patch_path_can_be_named(patch, path):
    paths = jd.nameable(patch, {})
    assert path in paths and "/dev/null" not in paths and not any(p.endswith("\r") for p in paths)


def test_cli_resume_of_a_judge_on_an_applied_job_exits_zero(tmp_path, monkeypatch):
    import importlib.util
    import yaml
    c = yaml.safe_load((ROOT / "config.yaml").read_text())
    c["roles"]["code_judge"]["model"] = "fake:scripted"
    (tmp_path / "c.yaml").write_text(yaml.safe_dump(c))
    env = Env(tmp_path, [submit(PASSED)], state=rj.APPLIED)
    real = jd.run_judge
    monkeypatch.setattr(jd, "run_judge", lambda **kw: (_ for _ in ()).throw(KeyboardInterrupt))
    with pytest.raises(KeyboardInterrupt):
        env.judge()
    monkeypatch.setattr(jd, "run_judge", real)
    spec = importlib.util.spec_from_file_location("argus_cli_judge", ROOT / "scripts" / "argus.py")
    cli = importlib.util.module_from_spec(spec)
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))         # as when the script runs (approve_draft beside it)
    spec.loader.exec_module(cli)
    rc = cli.main(["--config", str(tmp_path / "c.yaml"), "--jobs-dir", str(env.jobs), "resume", "jj"], deps=env.deps)
    assert rc == 0 and env.job().data["stages"]["j1"]["status"] == jd.JUDGED
