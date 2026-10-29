"""Router v0 (docs/reviews/SPEC_ROUTER_V0.md): `argus code` as one job, with scripted models and the drafter tests'
injected validation (no Docker): the job's states, its cap across stages, the cap a stage started with, the job lock,
approval bound to the draft the human saw, live confirmation and the key, and a job root of its own."""
import hashlib
import json
import os
import subprocess
import sys
import unicodedata
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
                            clock=lambda: "2026-10-23T00:00:00Z", echo=self.said.append, red=td.fake_red)

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


def test_the_approve_screen_and_status_say_how_many_old_tests_a_draft_changes(tmp_path):
    # W2a-ext K6: the number of changed test files and of K3 warnings, computed from the job's intake
    shown = []
    e = Env(tmp_path, confirm=lambda text: shown.append(text) or "approve" not in text)
    e.code()
    st, path = rj._last_draft(e.job())
    d = json.loads(path.read_text())
    d["changed_tests"] = [td.WEAKER_ENTRY]
    path.write_text(json.dumps(d))
    line = ("changes 1 existing test file(s) (tests/test_old.py), 4 warning(s): read the diff in DRAFT_REVIEW.md")
    assert line in rj.status("jtest", jobs_dir=e.jobs)
    with pytest.raises(rj.Refused, match="not confirmed"):
        e.approve()
    assert line in shown[-1] and e.coder.calls == []
    d.pop("changed_tests")
    path.write_text(json.dumps(d))
    assert "existing test file" not in rj.status("jtest", jobs_dir=e.jobs)


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


# ---- the key from a file, without a terminal (docs/reviews/SPEC_ROUTER_KEY_FILE.md) --------------------------------

KEY = "sk-ant-file-0000"


def key_file(tmp_path, content=KEY + "\n", mode=0o600, where=None):
    d = where or tmp_path / "secret"
    d.mkdir(parents=True, exist_ok=True)
    f = d / "key"
    f.write_text(content)
    os.chmod(f, mode)
    return f


def no_terminal(tmp_path, monkeypatch, **deps):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    shown = []
    e = Env(tmp_path, config=real_cfg(), confirm=lambda text: shown.append(text) or False)
    e.deps.isatty = lambda: False
    e.deps.get_key = lambda: pytest.fail("with --key-file no key is typed")
    for k, v in deps.items():
        setattr(e.deps, k, v)
    seen = []
    monkeypatch.setattr(cdr, "run_drafter", fake_draft_run(seen))
    return e, seen, shown


def test_a_key_file_runs_a_live_stage_without_a_terminal_and_the_key_is_never_written(tmp_path, monkeypatch):
    e, seen, shown = no_terminal(tmp_path, monkeypatch, key_file=key_file(tmp_path), assume_yes=True)
    e.code()
    assert seen == [{"ANTHROPIC_API_KEY": KEY, "ARGUS_LIVE": "1"}] and shown == []          # no [y/N] asked
    assert "ANTHROPIC_API_KEY" not in os.environ and "ARGUS_LIVE" not in os.environ
    log = e.job().data["log"]
    assert any(x["what"] == "confirmed_by_flag" and "job cap $1.00" in x["screen"] for x in log)  # the limits, kept
    assert [x["path"] for x in log if x["what"] == "key_from_file"] == [str(tmp_path / "secret" / "key")]
    assert any("job cap $1.00" in s and "(--yes: approved in chat" in s for s in e.said)        # and printed
    for f in e.job().dir.rglob("*"):
        if f.is_file():
            assert KEY.encode() not in f.read_bytes(), f


def test_a_key_file_without_yes_still_asks_y_n(tmp_path, monkeypatch):
    e, seen, shown = no_terminal(tmp_path, monkeypatch, key_file=key_file(tmp_path))
    with pytest.raises(rj.Refused, match="not confirmed"):
        e.code()
    assert len(shown) == 1 and seen == []


@pytest.mark.parametrize("make, why", [
    (lambda t, e: key_file(t, mode=0o644), "can be read by others"),
    (lambda t, e: key_file(t, mode=0o640), "can be read by others"),
    (lambda t, e: (lambda f: (t / "link").symlink_to(f) or t / "link")(key_file(t)), "is not a regular file"),
    (lambda t, e: t / "nosuch", "cannot be read"),
    (lambda t, e: key_file(t, where=e.jobs), "keep the key outside every repository and jobs/"),
    (lambda t, e: key_file(t, where=e.repo / "secret"), "keep the key outside every repository and jobs/"),
    (lambda t, e: key_file(t, content=""), "the key is empty"),
    (lambda t, e: key_file(t, content="sk-ant-a sk-ant-b\n"), "whitespace"),
    (lambda t, e: key_file(t, content="sk-ant-file-0000\n\n"), "whitespace"),
    (lambda t, e: key_file(t, content="not-a-key-file-0000"), "does not look like"),
])
def test_a_key_file_that_is_not_safe_or_not_a_key_starts_nothing_and_is_never_shown(tmp_path, monkeypatch, make, why):
    e, seen, shown = no_terminal(tmp_path, monkeypatch, assume_yes=True)
    e.deps.key_file = make(tmp_path, e)
    with pytest.raises(rj.Refused, match=why) as err:
        e.code()
    assert seen == [] and "ANTHROPIC_API_KEY" not in os.environ
    assert "sk-ant" not in str(err.value) and "not-a-key" not in str(err.value)


def test_a_key_file_of_another_user_starts_nothing(tmp_path, monkeypatch):
    e, seen, shown = no_terminal(tmp_path, monkeypatch, key_file=key_file(tmp_path), assume_yes=True)
    monkeypatch.setattr(rj.os, "getuid", lambda: os.stat(e.deps.key_file).st_uid + 1)     # as if another user ran it
    with pytest.raises(rj.Refused, match="is not owned by you"):
        e.code()
    assert seen == []


def test_yes_without_a_key_file_is_refused_and_no_terminal_without_one_still_is(tmp_path, monkeypatch):
    e, seen, shown = no_terminal(tmp_path, monkeypatch, assume_yes=True)
    with pytest.raises(rj.Refused, match="--yes needs --key-file"):
        e.code()
    e2, seen2, _ = no_terminal(tmp_path / "b", monkeypatch)
    with pytest.raises(rj.Refused, match="needs a terminal"):
        e2.code()
    assert seen == seen2 == []


def test_the_cli_passes_key_file_and_yes_to_the_live_commands_only(env, monkeypatch, tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("argus_cli_k", ROOT / "scripts" / "argus.py")
    cli = importlib.util.module_from_spec(spec)
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))         # as when the script runs (approve_draft beside it)
    spec.loader.exec_module(cli)
    got = {}
    monkeypatch.setattr(rj, "start_code", lambda **kw: got.update(kw) or (_ for _ in ()).throw(rj.Refused("stop")))
    f = key_file(tmp_path)
    rc = cli.main(["--jobs-dir", str(env.jobs), "code", "--repo", str(env.repo), "--commit", "HEAD", "--issue", "x",
                   "--key-file", str(f), "--yes"], deps=env.deps)
    assert rc == 2 and got["deps"].key_file == str(f) and got["deps"].assume_yes is True
    assert {rj.ROOT, env.jobs, env.repo} <= set(got["deps"].key_forbidden)
    with pytest.raises(SystemExit):
        cli.main(["status", "j", "--key-file", str(f)])                    # not a live command: no such option


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



def test_a_drafter_stage_is_bounded_by_dollars_not_by_re_sent_tokens():
    """Router pilot #1 on DeepSeek: the token ceiling (re-sent and cached inputs counted) ran out at $0.018 of $0.70."""
    s = rj.stage_config(load_config(), 0.75)
    lim = cdr.drafter_settings(s)
    assert lim["attempt_tokens"] == 2000000 and s["budget"]["max_tokens"] == 3000000 and lim["attempt_usd"] == 0.7



def test_after_a_failed_redraft_the_last_accepted_draft_is_still_approved_by_its_sha(tmp_path):
    """Router pilot #1: d3 was accepted, a redraft (d4) failed, and the job could not be approved any more."""
    e = Env(tmp_path, draft=[td.SUBMIT, reply("cut", stop_reason="max_tokens")])
    e.code()
    seen = e.sha()                                        # the draft of d1
    rj.redraft("jtest", cfg=e.cfg, deps=e.deps, jobs_dir=e.jobs)
    job = e.job()
    assert job.data["state"] == rj.DRAFT_FAILED and job.data["stages"]["d2"]["status"] == "NO_DRAFT"
    text = rj.status("jtest", jobs_dir=e.jobs)
    assert "the latest redraft failed; the last accepted draft is from jtest-d1" in text
    assert f"argus approve jtest --sha {seen}" in text
    job, r = e.approve(sha=seen)
    assert r["status"] == "DONE" and job.data["state"] == rj.REVIEW_READY
    assert job.data["approval"]["draft_sha256"].startswith(seen)


def test_a_failed_job_without_an_accepted_draft_cannot_be_approved(tmp_path):
    e = Env(tmp_path, draft=[reply("cut", stop_reason="max_tokens")])
    e.code()
    assert e.job().data["state"] == rj.DRAFT_FAILED
    assert "approve" not in rj.status("jtest", jobs_dir=e.jobs)
    with pytest.raises(rj.Refused, match="has no draft"):
        rj.approve("jtest", sha="0" * 12, cfg=e.cfg, deps=e.deps, sandbox_cfg={}, jobs_dir=e.jobs)
    assert e.coder.calls == []


# ---- decision times, apply commands and why a job failed (docs/reviews/SPEC_ROUTER_STATUS.md) ----------------------

def ticking():
    t = iter(range(10_000))
    return lambda: f"2026-10-24T00:00:{next(t):04d}Z"


def decisions(job):
    keep = ("limits_shown", "confirmed", "not_confirmed", "confirmed_by_flag", "key_typed", "key_from_file", "state")
    return [x["what"] + (":" + x["new"] if x["what"] == "state" else "") for x in job.data["log"] if x["what"] in keep]


def test_a_terminal_confirmation_and_a_typed_key_are_noted_with_their_times(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    e = Env(tmp_path, config=real_cfg())
    e.deps.get_key, e.deps.clock = (lambda: "sk-ant-test-0000"), ticking()
    monkeypatch.setattr(cdr, "run_drafter", fake_draft_run([]))
    e.code()
    job = e.job()
    assert decisions(job) == ["limits_shown", "confirmed", "key_typed", "state:DRAFTING", "state:DRAFT_FAILED"]
    at = {x["what"]: x["at"] for x in job.data["log"]}
    assert at["limits_shown"] < at["confirmed"] < at["key_typed"]                 # each with its own time
    assert any(x["what"] == "limits_shown" and "job cap $1.00" in x["screen"] for x in job.data["log"])
    assert set(next(x for x in job.data["log"] if x["what"] == "key_typed")) == {"at", "what"}   # nothing of the key


def test_not_confirming_is_noted_and_starts_nothing(tmp_path):
    e = Env(tmp_path, confirm=lambda text: False)
    with pytest.raises(rj.Refused, match="not confirmed"):
        e.code()
    job = e.job()
    assert decisions(job) == ["limits_shown", "not_confirmed"] and job.data["stages"] == {} and e.drafter.calls == []


@pytest.mark.parametrize("key", ["", "not-a-key", "sk-ant-a sk-ant-b"])
def test_a_refused_key_is_not_noted_as_typed(tmp_path, monkeypatch, key):
    e = Env(tmp_path, config=real_cfg())
    e.deps.get_key = lambda: key
    monkeypatch.setattr(cdr, "run_drafter", fake_draft_run([]))
    with pytest.raises(rj.Refused):
        e.code()
    assert decisions(e.job()) == ["limits_shown", "confirmed"]


def test_with_yes_the_flag_and_the_key_file_are_noted_not_a_terminal_answer(tmp_path, monkeypatch):
    e, _, _ = no_terminal(tmp_path, monkeypatch, key_file=key_file(tmp_path), assume_yes=True)
    e.code()
    assert decisions(e.job()) == ["limits_shown", "confirmed_by_flag", "key_from_file", "state:DRAFTING",
                                  "state:DRAFT_FAILED"]


def test_a_ready_review_says_where_it_is_its_patch_sha_and_how_to_apply_it(env):
    env.code()
    job, _ = env.approve()
    before = job.file.read_bytes()
    text = rj.status("jtest", jobs_dir=env.jobs)
    d = Path(job.data["stages"]["a1"]["review"]["dir"])
    patch, commit, repo = d / "changes.patch", job.data["intake"]["commit"], str(env.repo)
    assert len(commit) == 40 and commit != "HEAD"
    assert f"PR description: {d / 'PR.md'}" in text and (d / "PR.md").exists()
    assert f"patch:          {patch} (sha256 {hashlib.sha256(patch.read_bytes()).hexdigest()})" in text
    lines = text.splitlines()
    want = [f"  sha256sum {patch}", f"  git -C {repo} checkout -b argus/jtest {commit}",
            f"  git -C {repo} apply --check --whitespace=nowarn {patch}",
            f"  git -C {repo} apply --whitespace=nowarn {patch}"]
    assert lines[-4:] == want                                    # --check before apply
    assert job.file.read_bytes() == before                       # status only reads


def test_an_invalid_review_says_where_it_is_and_gives_no_apply_command(env):
    env.code()
    job, _ = env.approve()
    job.data["stages"]["a1"]["review"].update(valid=False, problems=["claims do not match"])
    job.data["state"] = rj.REVIEW_INVALID
    job.save()
    text = rj.status("jtest", jobs_dir=env.jobs)
    assert "NOT valid: claims do not match" in text and "PR description:" in text
    assert "apply" not in text and "checkout -b" not in text and "sha256sum" not in text


def test_branch_names_are_valid_for_every_job_id_shape():
    for job_id in (rj.new_job_id(), "j" + "z" * 40, "j" + "_" * 40, "j0"):
        assert rj.JOB_ID.match(job_id)
        out = subprocess.run(["git", "check-ref-format", "--branch", rj.branch_name(job_id)], capture_output=True)
        assert out.returncode == 0, job_id


def failed_agent(result):
    def run(*, run_id, runs_dir, **kw):
        d = Path(runs_dir) / run_id
        d.mkdir(parents=True, exist_ok=True)
        if result is not None:
            (d / "result.json").write_text(json.dumps(result))
        return {"status": "FAILED_ACCEPTANCE", "stop_reason": "stagnant: the same criteria failed 2 attempts in a row",
                "usd_billed": 0.0}
    return run


def test_a_failed_agent_says_why_what_failed_and_what_can_be_done(env, monkeypatch):
    env.code()
    monkeypatch.setattr(ctrun, "run_code_task", failed_agent(
        {"status": "FAILED_ACCEPTANCE", "attempts": 2, "verdict": {"failing": ["validation:target", "claims"]}}))
    job, _ = env.approve()
    before = job.file.read_bytes()
    text = rj.status("jtest", jobs_dir=env.jobs)
    assert "why: stagnant: the same criteria failed 2 attempts in a row" in text
    assert "agent result: FAILED_ACCEPTANCE, 2 attempt(s), failing: validation:target, claims" in text
    assert 'next: argus retry jtest  |  argus abandon jtest "<why>"' in text and "redraft" not in text
    assert job.file.read_bytes() == before


def test_a_failed_agent_without_its_result_is_still_shown(env, monkeypatch):
    env.code()
    monkeypatch.setattr(ctrun, "run_code_task", failed_agent(None))
    env.approve()
    text = rj.status("jtest", jobs_dir=env.jobs)
    assert "agent result: unreadable" in text and "why: stagnant" in text


def test_a_failed_draft_says_why_and_offers_redraft_or_reject(tmp_path):
    e = Env(tmp_path, draft=[reply("cut", stop_reason="max_tokens")])
    e.code()
    job = e.job()
    reason = [x for x in job.data["log"] if x.get("new") == rj.DRAFT_FAILED][-1]["reason"]
    text = rj.status("jtest", jobs_dir=e.jobs)
    assert reason and f"why: {reason}" in text
    assert 'next: argus redraft jtest  |  argus reject jtest "<why>"' in text


def test_a_blocked_job_says_why(tmp_path, env, monkeypatch):
    e = Env(tmp_path / "budget")
    with pytest.raises(rj.Refused):
        e.code(max_usd=0.30)
    text = rj.status("jtest", jobs_dir=e.jobs)
    assert "why: budget: $0.3000 left for the drafter" in text and 'next: argus abandon jtest "<why>"' in text
    env.code()
    monkeypatch.setattr(ctrun, "run_code_task", lambda **kw: (_ for _ in ()).throw(RuntimeError("crash")))
    with pytest.raises(RuntimeError):
        env.approve()
    monkeypatch.undo()
    path = env.job().root / "fixtures" / "contracts" / "task.json"
    c = json.loads(path.read_text())
    c["limits"]["max_iterations"] = 9
    path.write_text(json.dumps(c))
    with pytest.raises(rj.Refused):
        rj.resume("jtest", cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs)
    assert "why: contract_changed: the contract differs from the approved one" in rj.status("jtest", jobs_dir=env.jobs)


def test_a_rejected_or_abandoned_job_says_why_and_by_whom(tmp_path, monkeypatch):
    monkeypatch.setenv("USER", "atha")
    for i, fn in enumerate((rj.reject, rj.abandon)):
        e = Env(tmp_path / str(i))
        e.code()
        fn("jtest", "tests look wrong", deps=e.deps, jobs_dir=e.jobs)
        text = rj.status("jtest", jobs_dir=e.jobs)
        assert "why: tests look wrong (by atha)" in text and "next:" not in text


def test_text_from_a_model_is_printed_without_control_characters(env, monkeypatch):
    nasty = "\x1b[31mred\x1b[0m \x1b]0;fake title\x07ok\rover\nline\x7fend\x9b2J"
    env.code()
    monkeypatch.setattr(ctrun, "run_code_task", failed_agent(
        {"status": "FAILED_ACCEPTANCE", "attempts": 1, "verdict": {"failing": [nasty]}}))
    env.approve()
    job = env.job()
    [x for x in job.data["log"] if x.get("new") == rj.AGENT_FAILED][-1]["reason"] = nasty
    job.save()
    text = rj.status("jtest", jobs_dir=env.jobs)
    assert not [c for c in text.replace("\n", "") if unicodedata.category(c) == "Cc"]
    assert "red ok over line end" in text and "fake title" not in text
    assert rj.clean("a\x1bb") == "ab" and rj.clean("tab\there") == "tab here"
    screen = rj._limits_text(job, "approve", ["writable: " + nasty])          # the [y/N] screen, too
    assert "writable: red ok over line end" in screen and not [c for c in screen.replace("\n", "")
                                                                if unicodedata.category(c) == "Cc"]


# ---- retry: the agent again in the same job (docs/reviews/SPEC_AGENT_CONTEXT_RETRY.md 2.4, 2.5) ---------------------

A1 = {"status": "FAILED_ACCEPTANCE", "attempts": 2, "verdict": {"failing": ["validation:target", "claims"]},
      "attempt": {"iteration": 1, "end": "context_limit", "steps": 5, "wrote": False,
                  "read": ["src/shop.py", "tests/test_old.py"]}}
A1_ENDS = [{"event": "attempt_end", "iteration": 0, "reason": "context_limit", "steps": 6},
           {"event": "attempt_summary", "iteration": 0, "reason": "context_limit", "steps": 6, "wrote": False},
           {"event": "attempt_end", "iteration": 1, "reason": "context_limit", "steps": 5},
           {"event": "attempt_summary", "iteration": 1, "reason": "context_limit", "steps": 5, "wrote": False}]


def failed_a1(env, monkeypatch, result=A1, ends=A1_ENDS, verdict=None):
    """A job whose first agent stage failed like router pilot #3's: approved, then AGENT_FAILED."""
    env.code()

    def run(*, run_id, runs_dir, **kw):
        d = Path(runs_dir) / run_id
        d.mkdir(parents=True, exist_ok=True)
        if result is not None:
            (d / "result.json").write_text(json.dumps(result))
        (d / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in ends))
        if verdict is not None:
            (d / "verdict_1.json").write_text(json.dumps(verdict))
        return {"status": "FAILED_ACCEPTANCE", "stop_reason": "stagnant: the same criteria failed 2 attempts in a row",
                "usd_billed": 0.0}
    monkeypatch.setattr(ctrun, "run_code_task", run)
    env.approve()
    monkeypatch.undo()
    assert env.job().data["state"] == rj.AGENT_FAILED
    return env.job()


def retry(env, **kw):
    return rj.retry("jtest", cfg=env.cfg, deps=env.deps, sandbox_cfg={}, jobs_dir=env.jobs, **kw)


def first_request(model):
    return "\n".join(m.content if isinstance(m.content, str) else json.dumps(m.content)
                     for m in model.calls[0]["messages"])


def test_a_retry_runs_a_new_agent_stage_told_how_the_last_one_ended(env, monkeypatch):
    job = failed_a1(env, monkeypatch)
    left = rj.left_usd(job)
    profile = json.loads((job.root / "fixtures" / "contracts" / "task.json").read_text()).get("budget_profile")
    by = env.cfg["router"]["agent_max_usd"]
    job, r = retry(env)
    st = job.data["stages"]["a2"]
    assert r["status"] == "DONE" and job.data["state"] == rj.REVIEW_READY and st["run_id"] == "jtest-a2"
    assert st["cap_usd"] == round(min(by.get(profile, by["default"]), left), 6)
    assert st["carry"] == {"carried": True, "from": "a1", "stopped": {"end": "context_limit", "steps": 5,
                                                                      "wrote": False, "read": A1["attempt"]["read"]}}
    first = first_request(env.coder)
    assert "How the previous run of this task ended" in first
    assert "its last attempt ended context_limit after 5 steps; it changed no file." in first
    assert "Files it read: src/shop.py, tests/test_old.py." in first and "the writable files are src/shop.py" in first
    assert [e["new"] for e in job.data["log"] if e["what"] == "state"][-2:] == [rj.AGENT_RUNNING, rj.REVIEW_READY]
    assert any("retry the agent" in c and "a1 ended: context_limit after 5 steps, no file changed" in c
               for c in env.confirms)
    text = rj.status("jtest", jobs_dir=env.jobs)
    assert "  a1 attempts: 1 context_limit after 6 steps, no file changed; 2 context_limit after 5 steps, no file " \
           "changed" in text
    assert "  a2 attempts: 1 finished after 1 steps, files changed" in text
    assert f"review package: {job.runs / 'jtest-a2' / 'review'}" in text                 # the last agent stage


def test_a_retry_of_an_older_run_takes_wrote_from_its_last_verdict(env, monkeypatch):
    old = {k: v for k, v in A1.items()}
    old["attempt"] = {"iteration": 1, "end": "context_limit", "steps": 5}                 # pilot #3's a1
    verdict = {"criteria": [{"id": "scope:protected", "evidence": {"diff": {"added": [], "removed": [],
                                                                            "modified": []}}}]}
    failed_a1(env, monkeypatch, result=old, verdict=verdict)
    job, _ = retry(env)
    assert job.data["stages"]["a2"]["carry"]["stopped"] == {"end": "context_limit", "steps": 5, "wrote": False,
                                                            "read": []}
    first = first_request(env.coder)
    assert "It ran out of context before changing any file." in first and "Files it read" not in first


def test_a_retry_whose_previous_result_cannot_be_read_starts_nothing(env, monkeypatch):
    failed_a1(env, monkeypatch, result=None)
    with pytest.raises(rj.Refused, match="cannot be read"):
        retry(env)
    assert env.job().data["state"] == rj.AGENT_FAILED and "a2" not in env.job().data["stages"]
    assert env.coder.calls == []


def test_only_a_failed_agent_is_retried(env):
    env.code()
    with pytest.raises(rj.Refused, match="AWAITING_APPROVAL"):
        retry(env)
    env.approve()
    with pytest.raises(rj.Refused, match="REVIEW_READY"):
        retry(env)
    assert "a2" not in env.job().data["stages"]


def test_a_retry_that_cannot_fund_one_attempt_is_blocked(env, monkeypatch):
    failed_a1(env, monkeypatch)
    monkeypatch.setattr(rj, "left_usd", lambda job: 0.01)
    with pytest.raises(rj.Refused, match="not enough of the job cap"):
        retry(env)
    assert env.job().data["state"] == rj.BLOCKED and "a2" not in env.job().data["stages"] and env.coder.calls == []


def test_a_retry_on_a_changed_contract_is_blocked(env, monkeypatch):
    job = failed_a1(env, monkeypatch)
    path = job.root / "fixtures" / "contracts" / "task.json"
    c = json.loads(path.read_text())
    c["limits"]["max_iterations"] = 9
    path.write_text(json.dumps(c))
    with pytest.raises(rj.Refused, match="not the one approved"):
        retry(env)
    assert env.job().data["state"] == rj.BLOCKED and "a2" not in env.job().data["stages"] and env.coder.calls == []


def test_a_retry_not_confirmed_or_on_a_busy_job_starts_nothing(env, monkeypatch):
    job = failed_a1(env, monkeypatch)
    before = job.file.read_bytes()
    with job.lock():
        with pytest.raises(rj.JobBusy):
            retry(env)
    assert job.file.read_bytes() == before
    env.deps.confirm = lambda text: False
    with pytest.raises(rj.Refused, match="not confirmed"):
        retry(env)
    assert env.job().data["state"] == rj.AGENT_FAILED and "a2" not in env.job().data["stages"] and env.coder.calls == []


def test_a_resumed_retry_keeps_its_cap_and_what_it_carries(env, monkeypatch):
    failed_a1(env, monkeypatch)
    seen, real = [], ctrun.run_code_task

    def run(**kw):
        seen.append({k: kw[k] for k in ("run_id", "initial_feedback")} | {"cap": kw["cfg"]["budget"]["max_usd"]})
        if len(seen) == 1:
            raise RuntimeError("crash")
        return real(**kw)
    monkeypatch.setattr(ctrun, "run_code_task", run)
    with pytest.raises(RuntimeError):
        retry(env)
    assert env.job().data["state"] == rj.AGENT_RUNNING
    monkeypatch.setattr(rj, "left_usd", lambda job: 0.9)            # the job's money moved: the stage's cap does not
    _, r = rj.resume("jtest", cfg=env.cfg, deps=env.deps, sandbox_cfg={}, jobs_dir=env.jobs)
    assert r["status"] == "DONE" and seen[0] == seen[1] and seen[1]["run_id"] == "jtest-a2"
    assert seen[1]["initial_feedback"]["stopped"]["end"] == "context_limit"


def test_the_cli_retries_with_a_key_file(env, monkeypatch, tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("argus_cli_r", ROOT / "scripts" / "argus.py")
    cli = importlib.util.module_from_spec(spec)
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    spec.loader.exec_module(cli)
    got = {}
    monkeypatch.setattr(rj, "retry", lambda job_id, **kw: got.update(kw, job=job_id) or (_ for _ in ()).throw(
        rj.Refused("stop")))
    f = key_file(tmp_path)
    rc = cli.main(["--jobs-dir", str(env.jobs), "retry", "jtest", "--max-usd", "0.3", "--key-file", str(f), "--yes"],
                  deps=env.deps)
    assert rc == 2 and got["job"] == "jtest" and got["max_usd"] == 0.3 and got["deps"].key_file == str(f)


# ---- the review's outcome: applied in a commit, or rejected with why ----------------------------------------------

def _commit_patch(env, edit=None):
    patch = env.job().runs / "jtest-a1" / "review" / "changes.patch"
    td.git(env.repo, "apply", str(patch))
    if edit:
        edit()
    td.git(env.repo, "add", "-A")
    td.git(env.repo, "commit", "-qm", "apply the review package")
    return subprocess.run(["git", "-C", str(env.repo), "rev-parse", "HEAD"], capture_output=True, text=True,
                          check=True).stdout.strip()


def test_applied_records_the_commit_and_that_the_patch_went_in_as_it_was(env):
    env.code()
    env.approve()
    sha = _commit_patch(env)
    job = rj.applied("jtest", "HEAD", deps=env.deps, jobs_dir=env.jobs)
    e = job.data["log"][-1]
    assert job.data["state"] == rj.APPLIED and e["old"] == rj.REVIEW_READY and e["commit"] == sha
    assert e["as_is"] is True
    patch = job.runs / "jtest-a1" / "review" / "changes.patch"
    assert e["patch_sha256"] == hashlib.sha256(patch.read_bytes()).hexdigest()
    assert f"applied: commit {sha} (the patch as it was)" in rj.status("jtest", jobs_dir=env.jobs)
    with pytest.raises(rj.Refused, match="nothing to abandon"):
        rj.abandon("jtest", "late", deps=env.deps, jobs_dir=env.jobs)


def test_applied_tells_a_patch_rewritten_before_its_commit(env):
    env.code()
    env.approve()
    _commit_patch(env, edit=lambda: (env.repo / "src" / "shop.py").write_text(td.FIXED + "\n# touched by hand\n"))
    job = rj.applied("jtest", "HEAD", deps=env.deps, jobs_dir=env.jobs, note="comment added")
    assert job.data["log"][-1]["as_is"] is False
    assert "(changes that differ from the patch)" in rj.status("jtest", jobs_dir=env.jobs)


def test_applied_is_refused_for_an_unknown_commit_or_a_job_not_ready(env):
    env.code()
    with pytest.raises(rj.Refused, match="only a valid review package is applied"):
        rj.applied("jtest", "HEAD", deps=env.deps, jobs_dir=env.jobs)
    env.approve()
    for bad in ("0" * 40, "--output=/tmp/x"):
        with pytest.raises(rj.Refused, match="failed"):
            rj.applied("jtest", bad, deps=env.deps, jobs_dir=env.jobs)
    assert env.job().data["state"] == rj.REVIEW_READY


def test_a_review_package_rejected_says_why_and_cannot_be_applied_after(env):
    env.code()
    env.approve()
    rj.reject("jtest", "an attack test found two defects", deps=env.deps, jobs_dir=env.jobs)
    job = env.job()
    assert job.data["state"] == rj.REJECTED and job.data["log"][-1]["old"] == rj.REVIEW_READY
    assert "why: an attack test found two defects" in rj.status("jtest", jobs_dir=env.jobs)
    with pytest.raises(rj.Refused, match="REJECTED"):
        rj.applied("jtest", "HEAD", deps=env.deps, jobs_dir=env.jobs)


def test_the_cli_records_applied_and_prints_the_status(env, capsys):
    sys.path.insert(0, str(ROOT / "scripts"))
    import argus
    env.code()
    env.approve()
    sha = _commit_patch(env)
    assert argus.main(["--jobs-dir", str(env.jobs), "applied", "jtest", "--commit", sha[:10]], deps=env.deps) == 0
    assert f"applied: commit {sha}" in capsys.readouterr().out and env.job().data["state"] == rj.APPLIED
    assert argus.main(["--jobs-dir", str(env.jobs), "applied", "jtest", "--commit", sha], deps=env.deps) == 2


def test_status_shows_the_estimate_misses_of_a_stage(env, monkeypatch):
    """SPEC_ESTIMATE_REASONING E3: a stage whose ledger has estimate_miss events gets one line in status."""
    job = failed_a1(env, monkeypatch, ends=A1_ENDS + [
        {"event": "llm_call", "call_id": "c1", "status": "ok"}, {"event": "llm_call", "call_id": "c2", "status": "ok"},
        {"event": "estimate_miss", "call_id": "c2", "est_input": 1000, "input_tokens": 1250}])
    text = rj.status("jtest", jobs_dir=env.jobs)
    assert "  a1 estimate misses: 1 of 2 calls, max 1.25" in text
    assert "d1 estimate misses" not in text and job.data["stages"]["d1"]["run_id"]
