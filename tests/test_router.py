"""Router v0 (docs/reviews/SPEC_ROUTER_V0.md): `argus code` as one job, with scripted models and the drafter tests'
injected validation (no Docker): the job's states, its cap across stages, the cap a stage started with, the job lock,
approval bound to the draft the human saw, live confirmation and the key, and a job root of its own."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_drafter as td  # noqa: E402

from codetask import drafter as cdr  # noqa: E402
from codetask import run as ctrun  # noqa: E402
from models.fake import StrictScriptedChatModel, reply  # noqa: E402
from router import job as rj  # noqa: E402
from runner import load_config  # noqa: E402

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="the path jail and flock need posix; the VM runs these")

ROOT = Path(__file__).resolve().parent.parent
CLAIMS = [{"claim": "tests_pass", "evidence": "validation:regression"},
          {"claim": "issue_fixed", "evidence": "validation:target"},
          {"claim": "file_changed", "path": "src/shop.py"}]
WRITE = reply(tool_calls=[{"name": "WriteFile", "args": {"path": "src/shop.py", "content": td.FIXED}, "id": "w1"}],
              input_tokens=500, output_tokens=60)
FINISH = reply(tool_calls=[{"name": "Finish", "args": {"claims": CLAIMS, "summary": "floor at 0"}, "id": "f1"}],
               input_tokens=500, output_tokens=60)


def make_repo(tmp_path):
    repo = tmp_path / "shop_repo"
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "conftest.py").write_text("")
    (repo / "src" / "shop.py").write_text(td.BUGGY)
    (repo / "tests" / "test_old.py").write_text(td.OLD_TEST)
    td.git(tmp_path, "init", "-q", str(repo))
    td.git(repo, "add", "-A")
    td.git(repo, "commit", "-qm", "base")
    return repo


def cfg(**drafter):
    c = load_config()
    c["roles"]["drafter"]["model"] = "fake:scripted"
    c["roles"]["coder"]["model"] = "fake:scripted"
    c["drafter"].update(drafter)
    return c


class Env:
    def __init__(self, tmp_path, *, draft=None, agent=None, confirm=None, config=None):
        self.repo, self.jobs = make_repo(tmp_path), tmp_path / "jobs"
        self.drafter = StrictScriptedChatModel(script=list(draft or [td.SUBMIT]))
        self.coder = StrictScriptedChatModel(script=list(agent or [WRITE, FINISH]))
        self.confirms, self.said = [], []
        self.cfg = config or cfg()

        def yes(text):
            self.confirms.append(text)
            return True
        self.deps = rj.Deps(confirm=confirm or yes, get_key=lambda: "unused", isatty=lambda: True,
                            models={"drafter": self.drafter, "coder": self.coder}, validate=td.fake_validate,
                            preflight=lambda: (True, "ok"), env_preflight=lambda name: (True, "ok"),
                            clock=lambda: "2026-10-23T00:00:00Z", echo=self.said.append)

    def code(self, job_id="jtest", **kw):
        return rj.start_code(repo=self.repo, commit="HEAD", issue=td.ISSUE, cfg=self.cfg, deps=self.deps,
                             jobs_dir=self.jobs, job_id=job_id, **kw)

    def sha(self, job_id="jtest"):
        return rj.draft_sha(rj._last_draft(rj.open_job(job_id, self.jobs))[1])[:12]

    def approve(self, job_id="jtest", **kw):
        kw.setdefault("sha", self.sha(job_id))
        return rj.approve(job_id, cfg=self.cfg, deps=self.deps, sandbox_cfg={}, jobs_dir=self.jobs, **kw)

    def job(self, job_id="jtest"):
        return rj.open_job(job_id, self.jobs)


@pytest.fixture
def env(tmp_path):
    return Env(tmp_path)


# ---- the job, end to end ------------------------------------------------------------------------------------------

def test_a_job_drafts_waits_for_approval_then_runs_the_agent_and_builds_the_review(env):
    job = env.code()
    assert job.data["state"] == rj.AWAITING_APPROVAL and env.coder.calls == []     # no agent before approval
    text = rj.status("jtest", jobs_dir=env.jobs)
    sha = env.sha()
    assert f"draft {sha}" in text and f"argus approve jtest --sha {sha}" in text and "writable: src/shop.py" in text
    job, r = env.approve()
    assert r["status"] == "DONE" and job.data["state"] == rj.REVIEW_READY
    ap = job.data["approval"]
    assert ap["draft_sha256"].startswith(sha) and ap["feasibility"] == "unproven" and len(ap["contract_sha256"]) == 64
    assert job.data["stages"]["a1"]["review"]["valid"] is True
    assert (job.runs / "jtest-a1" / "review" / "changes.patch").exists()
    assert [e["new"] for e in job.data["log"] if e["what"] == "state"] == [
        rj.DRAFTING, rj.AWAITING_APPROVAL, rj.AGENT_RUNNING, rj.REVIEW_READY]
    assert any("writable: src/shop.py" in c and f"draft {sha}" in c for c in env.confirms)   # the approve screen


def test_a_job_has_its_own_root_and_never_writes_the_checkouts_fixtures(env):
    before = sorted(p.name for p in (ROOT / "fixtures" / "intake").iterdir())
    env.code()
    env.approve()
    job = env.job()
    assert (job.root / "fixtures" / "intake" / "base.json").exists() and (job.root / "fixtures" / "contracts" / "task.json").exists()
    assert sorted(p.name for p in (ROOT / "fixtures" / "intake").iterdir()) == before
    assert not (ROOT / "fixtures" / "contracts" / "task.json").exists()


def test_jobs_are_ignored_by_git():
    out = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", "jobs/jx/job.json"])
    assert out.returncode == 0


def test_the_agent_never_starts_without_approval(env):
    env.code()
    with pytest.raises(rj.Refused, match="nothing to resume"):
        rj.resume("jtest", cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs)
    with pytest.raises(rj.Refused, match="already exists"):
        env.code()
    assert env.coder.calls == [] and env.job().data["state"] == rj.AWAITING_APPROVAL


def test_a_rejected_job_cannot_be_approved(env):
    env.code()
    rj.reject("jtest", "tests look wrong", deps=env.deps, jobs_dir=env.jobs)
    with pytest.raises(rj.Refused, match="REJECTED"):
        env.approve()
    assert env.coder.calls == [] and env.job().data["state"] == rj.REJECTED and env.job().data["approval"] is None
    assert not (env.job().root / "fixtures" / "contracts" / "task.json").exists()     # nothing was approved


def test_not_confirming_starts_nothing(tmp_path):
    e = Env(tmp_path, confirm=lambda text: False)
    with pytest.raises(rj.Refused, match="not confirmed"):
        e.code()
    job = e.job()
    assert job.data["state"] == rj.NEW and job.data["stages"] == {} and e.drafter.calls == []


# ---- money across the job's stages ------------------------------------------------------------------------------

def test_the_agent_cap_is_the_lower_of_its_profile_and_what_the_job_has_left(env):
    env.code()
    left = rj.left_usd(env.job())
    job, _ = env.approve()
    assert job.data["approval"]["max_usd"] == round(min(0.75, left), 6) == job.data["stages"]["a1"]["cap_usd"]
    contract = json.loads((job.root / "fixtures" / "contracts" / "task.json").read_text())
    assert contract["limits"]["max_usd"] == job.data["approval"]["max_usd"]


def test_a_stage_that_cannot_fund_one_attempt_is_not_started(tmp_path):
    e = Env(tmp_path, config=cfg(attempt_usd=0.05))
    e.code(max_usd=0.10)                                  # the drafter fits ($0.05 of $0.10); the agent ($0.225) cannot
    with pytest.raises(rj.Refused, match="not enough of the job cap"):
        e.approve()
    assert e.coder.calls == [] and e.job().data["state"] == rj.BLOCKED and "a1" not in e.job().data["stages"]


def test_a_drafter_that_cannot_be_funded_is_not_started(tmp_path):
    e = Env(tmp_path)
    with pytest.raises(rj.Refused, match="not enough of the job cap"):
        e.code(max_usd=0.30)                              # one drafter attempt is $0.70
    assert e.drafter.calls == [] and e.job().data["state"] == rj.BLOCKED


def test_spend_is_counted_across_stages(env):
    env.code()
    job = env.job()
    drafted = rj.spent_nano(job)
    assert drafted > 0
    env.approve()
    assert rj.spent_nano(env.job()) > drafted


def test_a_resumed_stage_keeps_the_cap_it_started_with(env, monkeypatch):
    """A crash in the agent's stage, then more spend recorded and a lower job cap: the resume runs with the stage's
    recorded cap, not one recomputed from what is left (that would count the stage's own spend twice)."""
    env.code()
    real = ctrun.run_code_task
    calls = []

    def crash_once(**kw):
        calls.append(kw)
        if len(calls) == 1:
            raise RuntimeError("simulated crash")
        return real(**kw)
    monkeypatch.setattr(ctrun, "run_code_task", crash_once)
    with pytest.raises(RuntimeError):
        env.approve()
    job = env.job()
    cap = job.data["stages"]["a1"]["cap_usd"]
    assert job.data["state"] == rj.AGENT_RUNNING
    job.data["max_usd"] = 0.05                             # less left than the stage started with
    job.save()
    _, r = rj.resume("jtest", cfg=env.cfg, deps=env.deps, sandbox_cfg={}, jobs_dir=env.jobs)
    assert calls[1]["cfg"]["budget"]["max_usd"] == cap == calls[0]["cfg"]["budget"]["max_usd"]
    assert calls[1]["run_id"] == calls[0]["run_id"] == "jtest-a1"
    assert r["status"] == "DONE" and env.job().data["state"] == rj.REVIEW_READY


def test_a_resumed_drafter_keeps_its_cap_and_its_run(env, monkeypatch):
    real = cdr.run_drafter
    calls = []

    def crash_once(**kw):
        calls.append(kw)
        if len(calls) == 1:
            real(**kw)                                     # the run happened ...
            raise RuntimeError("simulated crash")          # ... but the job never heard of it
        return real(**kw)
    monkeypatch.setattr(cdr, "run_drafter", crash_once)
    with pytest.raises(RuntimeError):
        env.code(max_usd=0.72)                             # the stage starts with $0.72, below draft_max_usd ($0.75)
    job = env.job()
    assert job.data["state"] == rj.DRAFTING
    cap = job.data["stages"]["d1"]["cap_usd"]
    assert cap == 0.72
    job.data["max_usd"] = 5.0                              # a higher job cap must not raise the stage's
    job.save()
    rj.resume("jtest", cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs)
    assert calls[1]["max_usd"] == cap and calls[1]["cfg"]["budget"]["max_usd"] == cap
    assert calls[1]["resume"] is True and calls[1]["run_id"] == "jtest-d1"
    assert env.job().data["state"] == rj.AWAITING_APPROVAL


# ---- the job lock --------------------------------------------------------------------------------------------------

def test_a_second_command_on_a_job_in_use_is_refused_and_changes_nothing(env):
    env.code()
    before = env.job().file.read_text()
    holder = env.job()
    with holder.lock():                                   # e.g. an agent stage running in another terminal
        for cmd in (lambda: env.approve(),
                    lambda: rj.redraft("jtest", cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs),
                    lambda: rj.reject("jtest", "x", deps=env.deps, jobs_dir=env.jobs),
                    lambda: rj.resume("jtest", cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs)):
            with pytest.raises(rj.JobBusy, match="in use by another command"):
                cmd()
        assert "AWAITING_APPROVAL" in rj.status("jtest", jobs_dir=env.jobs)    # status only reads
    assert env.job().file.read_text() == before and env.coder.calls == []
    env.approve()                                          # released: the next command takes the lock
    assert env.job().data["state"] == rj.REVIEW_READY


def test_a_crashed_holder_releases_the_lock(env, tmp_path):
    env.code()
    lock = env.job().dir / ".lock"
    code = ("import fcntl, os, sys; fd = os.open(sys.argv[1], os.O_RDWR); fcntl.flock(fd, fcntl.LOCK_EX); os._exit(9)")
    assert subprocess.run([sys.executable, "-c", code, str(lock)]).returncode == 9
    env.approve()
    assert env.job().data["state"] == rj.REVIEW_READY


# ---- approval bound to the draft the human saw --------------------------------------------------------------------

def test_approve_needs_the_sha_of_the_draft_status_shows(env):
    env.code()
    for bad in ("", "0" * 12, env.sha()[:8]):
        with pytest.raises(rj.Refused, match="approve the draft status shows"):
            env.approve(sha=bad)
    assert env.coder.calls == []


def test_a_draft_changed_after_status_is_refused(env):
    env.code()
    seen = env.sha()
    st, path = rj._last_draft(env.job())
    d = json.loads(path.read_text())
    d["contract"]["scope"]["writable"].append("src/other.py")
    path.write_text(json.dumps(d))
    with pytest.raises(rj.Refused, match="not the"):
        env.approve(sha=seen)
    assert env.coder.calls == [] and env.job().data["approval"] is None


def test_a_draft_changed_while_the_approve_screen_is_read_is_refused(tmp_path):
    holder = {}

    def edit_then_yes(text):
        if "approve" in text:
            st, path = rj._last_draft(rj.open_job("jtest", holder["e"].jobs))
            d = json.loads(path.read_text())
            d["unverifiable"] = ["changed under the human"]
            path.write_text(json.dumps(d))
        return True
    e = Env(tmp_path, confirm=edit_then_yes)
    holder["e"] = e
    e.code()
    with pytest.raises(rj.Refused, match="changed after it was shown"):
        e.approve()
    assert e.coder.calls == [] and e.job().data["approval"] is None


def test_a_contract_changed_after_approval_blocks_the_agent(env, monkeypatch):
    env.code()
    monkeypatch.setattr(ctrun, "run_code_task", lambda **kw: (_ for _ in ()).throw(RuntimeError("crash")))
    with pytest.raises(RuntimeError):
        env.approve()
    monkeypatch.undo()
    job = env.job()
    path = job.root / "fixtures" / "contracts" / "task.json"
    c = json.loads(path.read_text())
    c["limits"]["max_iterations"] = 9
    path.write_text(json.dumps(c))
    with pytest.raises(rj.Refused, match="not the one approved"):
        rj.resume("jtest", cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs)
    assert env.job().data["state"] == rj.BLOCKED and env.coder.calls == []


# ---- live stages and the key ---------------------------------------------------------------------------------------

def real_cfg():
    c = cfg()
    c["roles"]["drafter"]["model"] = "anthropic:claude-sonnet-5-5"
    return c


def fake_draft_run(seen):
    def run(**kw):
        seen.append({k: os.environ.get(k) for k in ("ANTHROPIC_API_KEY", "ARGUS_LIVE")})
        return {"status": "NO_DRAFT", "stop_reason": "stub", "usd_billed": 0.0}
    return run


@pytest.mark.parametrize("key, why", [("", "empty"), ("not-a-key", "does not look like"),
                                      ("sk-ant-a sk-ant-b", "whitespace"), ("sk-ant-ask-ant-b", "does not look like")])
def test_a_bad_key_starts_nothing(tmp_path, monkeypatch, key, why):
    e = Env(tmp_path, config=real_cfg())
    e.deps.get_key = lambda: key
    seen = []
    monkeypatch.setattr(cdr, "run_drafter", fake_draft_run(seen))
    with pytest.raises(rj.Refused, match=why):
        e.code()
    assert seen == [] and e.job().data["stages"] == {} and "ANTHROPIC_API_KEY" not in os.environ


def test_the_key_is_set_only_during_the_stage_and_never_written(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    e = Env(tmp_path, config=real_cfg())
    e.deps.get_key = lambda: "sk-ant-test-0000"
    seen = []
    monkeypatch.setattr(cdr, "run_drafter", fake_draft_run(seen))
    e.code()
    assert seen == [{"ANTHROPIC_API_KEY": "sk-ant-test-0000", "ARGUS_LIVE": "1"}]
    assert "ANTHROPIC_API_KEY" not in os.environ and "ARGUS_LIVE" not in os.environ
    for f in e.job().dir.rglob("*"):
        if f.is_file():
            assert b"sk-ant-test-0000" not in f.read_bytes(), f


def test_a_live_stage_without_a_terminal_is_refused(tmp_path, monkeypatch):
    e = Env(tmp_path, config=real_cfg())
    e.deps.isatty = lambda: False
    seen = []
    monkeypatch.setattr(cdr, "run_drafter", fake_draft_run(seen))
    with pytest.raises(rj.Refused, match="needs a terminal"):
        e.code()
    assert seen == []


def test_the_cli_runs_a_job_and_prints_the_approve_command(env, capsys):
    import importlib.util
    spec = importlib.util.spec_from_file_location("argus_cli", ROOT / "scripts" / "argus.py")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(ROOT / "scripts"))
    spec.loader.exec_module(mod)
    issue = env.repo.parent / "issue.txt"
    issue.write_text(td.ISSUE)
    env.cfg = None
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(mod, "load_config", lambda path=None: cfg())
        rc = mod.main(["--jobs-dir", str(env.jobs), "code", "--repo", str(env.repo), "--commit", "HEAD",
                       "--issue-file", str(issue)], deps=env.deps)
    out = capsys.readouterr().out
    assert rc == 0 and "AWAITING_APPROVAL" in out and "argus approve j" in out



# ---- after router pilot #1 ----------------------------------------------------------------------------------------

def test_each_stage_says_it_is_running_and_how_to_continue_it(env):
    env.code()
    env.approve()
    running = [m for m in env.said if "running in" in m]
    assert len(running) == 2 and all("argus resume jtest" in m and "Do not start another job" in m for m in running)
    assert any(m.startswith("drafter finished: DRAFTED") for m in env.said)
    assert any(m.startswith("agent finished: DONE") for m in env.said)


def test_status_and_the_job_ledger_never_change_a_log(env):
    env.code()
    job = env.job()
    log = job.runs / "jtest-d1" / "events.jsonl"
    log.write_bytes(log.read_bytes() + b'{"event": "llm_call_started", "call_id": "cut", "wor')   # a stage mid-write
    before = log.read_bytes()
    rj.status("jtest", jobs_dir=env.jobs)
    rj.spent_nano(job)
    assert log.read_bytes() == before


def test_a_stale_job_is_abandoned_and_then_cannot_be_continued(env, monkeypatch):
    def stop(**kw):
        raise KeyboardInterrupt
    monkeypatch.setattr(cdr, "run_drafter", stop)
    with pytest.raises(KeyboardInterrupt):
        env.code()
    assert env.job().data["state"] == rj.DRAFTING
    with env.job().lock():                                 # still running somewhere: not under its feet
        with pytest.raises(rj.JobBusy):
            rj.abandon("jtest", "started again", deps=env.deps, jobs_dir=env.jobs)
    job = rj.abandon("jtest", "started again by mistake", deps=env.deps, jobs_dir=env.jobs)
    assert job.data["state"] == rj.ABANDONED and job.data["log"][-1]["reason"] == "started again by mistake"
    monkeypatch.undo()
    with pytest.raises(rj.Refused, match="nothing to resume"):
        rj.resume("jtest", cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs)
    with pytest.raises(rj.Refused, match="nothing to abandon"):
        rj.abandon("jtest", "again", deps=env.deps, jobs_dir=env.jobs)


def test_a_finished_job_cannot_be_abandoned(env):
    env.code()
    env.approve()
    with pytest.raises(rj.Refused, match="nothing to abandon"):
        rj.abandon("jtest", "x", deps=env.deps, jobs_dir=env.jobs)


def test_an_interrupted_command_says_how_to_continue(env, capsys, monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location("argus_cli2", ROOT / "scripts" / "argus.py")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(ROOT / "scripts"))
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "load_config", lambda path=None: cfg())
    monkeypatch.setattr(rj, "resume", lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt()))
    rc = mod.main(["--jobs-dir", str(env.jobs), "resume", "jtest"], deps=env.deps)
    err = capsys.readouterr().err
    assert rc == 130 and "argus resume jtest" in err and "Do not start a new job" in err
