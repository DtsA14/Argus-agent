"""SPEC_PRD_QUEUE part A: `argus queue` (router/queue.py): issues in order on one repository, each on the commit the one before was
applied as; the human approves the list and the money once; `step` makes at most one drafter run and never approves or applies;
a failure stops the queue; a job that can still spend holds its whole cap, an applied or finished one what it spent (SPEC_QUEUE_MONEY)."""
import json
import shutil
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_drafter as td  # noqa: E402
import test_router as tr  # noqa: E402
from router import job as rj  # noqa: E402
from router import queue as rq  # noqa: E402

ENV = "pwa_node22"


def git(repo, *args):
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@x", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env, text=True).stdout.strip()


class Q:
    def __init__(self, tmp_path, monkeypatch, *, confirm=None):
        self.env = tr.Env(tmp_path, draft=[td.SUBMIT] * 6, confirm=confirm)
        self.cfg = self.env.cfg
        self.cfg["issue_writer"]["repos"] = {"demo": {"path": str(self.env.repo), "environment": ENV}}
        self.cfg["issue_writer"]["code_max_usd"] = 1.0
        self.queues, self.jobs, self.repo = tmp_path / "queues", self.env.jobs, self.env.repo
        self.calls, real = [], rj.start_code

        def fake(**kw):                                 # the real start_code, without a sandbox environment to pin
            self.calls.append(dict(kw))
            kw["environment"] = None
            return real(**kw)
        monkeypatch.setattr(rj, "start_code", fake)

    def new(self, n=3, max_usd=3.0, **kw):
        kw.setdefault("issues", [f"{td.ISSUE}\n\nitem {i}" for i in range(1, n + 1)])
        kw.setdefault("repo", "demo")
        kw.setdefault("commit", "HEAD")
        return rq.new(max_usd=max_usd, cfg=self.cfg, deps=self.env.deps, queues_dir=self.queues, jobs_dir=self.jobs, **kw)

    def go(self, q):
        return rq.go(q["id"], sha=rq.list_sha(q)[:12], deps=self.env.deps, queues_dir=self.queues)

    def ready(self, n=3, max_usd=3.0):
        return self.go(self.new(n, max_usd))

    def step(self, q):
        return rq.step(q["id"], cfg=self.cfg, deps=self.env.deps, queues_dir=self.queues, jobs_dir=self.jobs)

    def q(self, q):
        return json.loads((self.queues / q["id"] / "queue.json").read_text())

    def status(self, q):
        return rq.status_lines(self.q(q), jobs_dir=self.jobs).splitlines()[0].split()[2]

    def job(self, q, i):
        return rj.open_job(self.q(q)["items"][i]["job"], self.jobs)

    def set_state(self, job, state, **log):
        with job.lock():
            old = job.data["state"]
            job.data["state"] = state
            job.data["log"].append({"at": "t", "what": "state", "old": old, "new": state, **log})
            job.save()

    def apply(self, q, i):
        """The item's job applied as the patch: a commit in the repository and the APPLIED entry `argus apply` writes."""
        git(self.repo, "commit", "-q", "--allow-empty", "-m", f"applied {i}")
        sha = git(self.repo, "rev-parse", "HEAD")
        self.set_state(self.job(q, i), rj.APPLIED, commit=sha, as_is=True)
        return sha


@pytest.fixture
def qe(tmp_path, monkeypatch):
    return Q(tmp_path, monkeypatch)


def read(path):
    return Path(path).read_bytes()


# ---- new and go ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("kw,why", [
    ({"repo": "nope"}, "is not one of issue_writer.repos"),
    ({"max_usd": 5.01}, "at most"), ({"max_usd": 0}, "at most"), ({"max_usd": 0.5}, "less than one job's cap"),
    ({"issues": []}, "1 to 8 issues"), ({"issues": ["x"] * 9}, "1 to 8 issues"), ({"issues": ["  "]}, "is empty"),
])
def test_new_refuses_a_bad_queue_and_writes_nothing(qe, kw, why):
    with pytest.raises(rj.Refused, match=why):
        qe.new(**({"max_usd": 3.0} | kw))
    assert not qe.queues.exists() or not list(qe.queues.glob("q*"))


def test_new_refuses_the_argus_checkout_and_a_commit_that_is_not_head(qe):
    qe.cfg["issue_writer"]["repos"]["argus"] = {"path": str(rj.ROOT), "environment": ENV}
    with pytest.raises(rj.Refused, match="never runs on the Argus checkout"):
        qe.new(repo="argus")
    first = git(qe.repo, "rev-parse", "HEAD")
    git(qe.repo, "commit", "-q", "--allow-empty", "-m", "later")
    with pytest.raises(rj.Refused, match="HEAD"):
        qe.new(commit=first)


def test_two_unfinished_queues_on_one_repository_are_refused_even_under_two_names(qe):
    qe.new()
    qe.cfg["issue_writer"]["repos"]["alias"] = {"path": str(qe.repo) + "/../" + qe.repo.name, "environment": ENV}
    with pytest.raises(rj.Refused, match="two queues would race"):
        qe.new(repo="alias")


def test_step_wants_the_approval_of_the_list_and_the_money(qe):
    q = qe.new()
    with pytest.raises(rj.Refused, match="not approved"):
        qe.step(q)
    with pytest.raises(rj.Refused, match="not the"):
        rq.go(q["id"], sha="0" * 12, deps=qe.env.deps, queues_dir=qe.queues)
    assert qe.q(q)["approved"] is None and qe.calls == [] and qe.status(q) == "PENDING"
    qe.go(q)
    assert qe.q(q)["approved"]["sha"] == rq.list_sha(qe.q(q))


@pytest.mark.parametrize("field,value", [("max_usd", 4.0), ("job_cap_usd", 0.5), ("environment", "other"), ("base_commit", "a" * 40)])
def test_a_list_changed_after_go_is_refused(qe, field, value):
    q = qe.ready()
    d = qe.queues / q["id"]
    data = qe.q(q)
    data[field] = value
    (d / "queue.json").write_text(json.dumps(data))
    with pytest.raises(rj.Refused, match="changed since"):
        qe.step(q)
    assert qe.calls == []


def test_an_issue_file_changed_after_go_is_refused(qe):
    q = qe.ready()
    (qe.queues / q["id"] / "issue-2.md").write_text("another issue")
    with pytest.raises(rj.Refused, match="issue 2"):
        qe.step(q)
    assert qe.calls == []


# ---- step ---------------------------------------------------------------------------------------------------------

def test_step_starts_one_code_job_on_the_base_commit_and_a_second_step_starts_nothing(qe):
    q = qe.ready()
    base = qe.q(q)["base_commit"]
    out = qe.step(q)
    (kw,) = qe.calls
    assert kw["environment"] == ENV and kw["commit"] == base and kw["max_usd"] == 1.0 and kw["issue"] == qe.job(q, 0).data["inputs"]["issue"]
    assert qe.job(q, 0).data["state"] == rj.AWAITING_APPROVAL and "argus approve" in out and "--sha" in out
    qe.step(q)
    assert len(qe.calls) == 1 and qe.q(q)["items"][1]["job"] is None
    assert qe.status(q) == "WAITING"


def test_the_next_issue_starts_on_the_commit_the_previous_was_applied_as(qe):
    q = qe.ready()
    qe.step(q)
    sha = qe.apply(q, 0)
    qe.step(q)
    assert qe.calls[1]["commit"] == sha and qe.job(q, 1).data["inputs"]["commit"] == sha
    assert qe.job(q, 1).data["state"] == rj.AWAITING_APPROVAL


def test_head_that_moved_stops_the_queue_before_the_next_item_starts(qe):
    q = qe.ready()
    qe.step(q)
    qe.apply(q, 0)
    git(qe.repo, "commit", "-q", "--allow-empty", "-m", "someone else")
    out = qe.step(q)
    assert "HEAD moved" in out and qe.status(q) == "STOPPED" and len(qe.calls) == 1


def test_a_commit_that_is_not_the_patch_stops_the_queue(qe):
    q = qe.ready()
    qe.step(q)
    git(qe.repo, "commit", "-q", "--allow-empty", "-m", "by hand")
    sha = git(qe.repo, "rev-parse", "HEAD")
    qe.set_state(qe.job(q, 0), rj.APPLIED, commit=sha, as_is=False)
    assert "as_is" in qe.step(q) and len(qe.calls) == 1


@pytest.mark.parametrize("state", [rj.REJECTED, rj.ABANDONED, rj.DRAFT_FAILED, rj.AGENT_FAILED, rj.BLOCKED, rj.REVIEW_INVALID])
def test_a_failed_item_stops_the_whole_queue(qe, state):
    q = qe.ready()
    qe.step(q)
    qe.set_state(qe.job(q, 0), state)
    out = qe.step(q)
    assert qe.status(q) == "STOPPED" and f"is {state}" in out and len(qe.calls) == 1


def test_a_recoverable_failure_continues_without_any_stored_state(qe):
    q = qe.ready()
    qe.step(q)
    qe.set_state(qe.job(q, 0), rj.DRAFT_FAILED)
    assert qe.status(q) == "STOPPED"
    qe.set_state(qe.job(q, 0), rj.AWAITING_APPROVAL)
    assert qe.status(q) == "WAITING" and "status" not in qe.q(q)


def test_every_item_applied_is_done_and_step_does_nothing(qe):
    q = qe.ready(n=2)
    for i in range(2):
        qe.step(q)
        qe.apply(q, i)
    assert qe.status(q) == "DONE"
    qe.step(q)
    assert len(qe.calls) == 2


def test_step_never_approves_or_applies(qe, monkeypatch):
    from router import apply as ra

    def boom(*a, **k):
        raise AssertionError("the queue called a human's command")
    for mod, name in ((rj, "approve"), (rj, "applied"), (rj, "_record_applied"), (ra, "apply")):
        monkeypatch.setattr(mod, name, boom)
    q = qe.ready()
    qe.step(q)
    qe.step(q)
    assert qe.job(q, 0).data["state"] == rj.AWAITING_APPROVAL


def test_status_writes_nothing_even_past_a_job_that_will_be_forgotten(qe):
    q = qe.ready()
    data = qe.q(q)
    data["items"][0]["job"] = "j20260101_000000_dead"          # recorded, never made
    (qe.queues / q["id"] / "queue.json").write_text(json.dumps(data))
    before = {p: read(p) for p in qe.queues.rglob("*") if p.is_file()}
    rq.status(q["id"], queues_dir=qe.queues, jobs_dir=qe.jobs)
    assert {p: read(p) for p in qe.queues.rglob("*") if p.is_file()} == before and not qe.jobs.exists()


# ---- a start that was cut off ---------------------------------------------------------------------------------------

def test_a_job_id_recorded_but_never_made_starts_exactly_one_job(qe):
    q = qe.ready()
    data = qe.q(q)
    data["items"][0]["job"] = "j20260101_000000_dead"
    (qe.queues / q["id"] / "queue.json").write_text(json.dumps(data))
    qe.step(q)
    assert len(qe.calls) == 1 and qe.q(q)["items"][0]["job"] != "j20260101_000000_dead"
    qe.step(q)
    assert len(qe.calls) == 1


def test_a_declined_confirmation_leaves_a_job_the_next_step_abandons_and_starts_again(tmp_path, monkeypatch):
    answer = [False]
    qe = Q(tmp_path, monkeypatch, confirm=lambda text: answer[0])
    q = qe.ready()
    with pytest.raises(rj.Refused):
        qe.step(q)
    stuck = qe.q(q)["items"][0]["job"]
    assert qe.job(q, 0).data["state"] == rj.NEW and not qe.job(q, 0).data["stages"]
    answer[0] = True
    qe.step(q)
    assert rj.open_job(stuck, qe.jobs).data["state"] == rj.ABANDONED
    assert qe.q(q)["items"][0]["job"] != stuck and qe.job(q, 0).data["state"] == rj.AWAITING_APPROVAL and len(qe.calls) == 2


def test_a_recorded_job_that_is_not_the_queues_issue_stops_the_queue_and_is_not_forgotten(qe):
    q = qe.ready()
    other = qe.env.code("jother")
    data = qe.q(q)
    data["items"][0]["job"] = other.id
    (qe.queues / q["id"] / "queue.json").write_text(json.dumps(data))
    out = qe.step(q)
    assert "is not this queue's issue" in out and qe.q(q)["items"][0]["job"] == other.id and len(qe.calls) == 1 and qe.env.job("jother").data["state"] != rj.ABANDONED


# ---- money ----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("state,counts_cap", [(rj.APPLIED, False), (rj.REJECTED, True), (rj.DRAFT_FAILED, True), (rj.AGENT_FAILED, True),
                                              (rj.AWAITING_APPROVAL, True), (rj.ABANDONED, False), (rj.BLOCKED, False), (rj.REVIEW_INVALID, False)])
def test_a_job_holds_its_whole_cap_unless_no_step_of_the_queue_can_spend_on_it_again(qe, state, counts_cap):
    q = qe.ready()
    qe.step(q)
    job = qe.job(q, 0)
    qe.set_state(job, state)
    assert rq.committed_nano(qe.job(q, 0)) == (1_000_000_000 if counts_cap else rj.spent_nano(qe.job(q, 0)))
    assert counts_cap or rj.spent_nano(qe.job(q, 0)) > 0          # the fake drafter spent something: "spent" and "zero" differ


def test_two_applied_jobs_hold_what_they_spent_and_the_third_issue_steps(qe):
    q = qe.ready(n=3, max_usd=2.0)                       # the pilot's shape: money of issues x cap would be $3.00, here $2.00 and one $1.00 job each
    for i in range(2):
        qe.step(q)
        qe.apply(q, i)
    held = sum(rq.committed_nano(qe.job(q, i)) for i in range(2))
    assert 0 < held < 100_000_000                        # what the fake drafter spent, not $2.00
    out = qe.step(q)
    assert "the money" not in out and len(qe.calls) == 3 and qe.status(q) == "WAITING"


def test_a_later_judge_of_an_applied_job_is_counted_once_it_has_happened(qe):
    q = qe.ready(n=1, max_usd=1.0)
    qe.step(q)
    qe.apply(q, 0)
    job = qe.job(q, 0)
    before = rq.committed_nano(job)
    first = next(iter(job.data["stages"].values()))
    shutil.copytree(job.runs / first["run_id"], job.runs / "judge-run")      # a judge's run: a ledger of its own, registered as a stage
    job.data["stages"]["j1"] = {**first, "kind": "judge", "run_id": "judge-run"}
    job.save()
    assert rq.committed_nano(qe.job(q, 0)) == 2 * before             # spent_nano adds every stage: nothing filters a judge out, and it counts only once it exists


# ---- close ----------------------------------------------------------------------------------------------------------

def test_a_closed_queue_never_steps_and_no_job_is_touched(qe):
    q = qe.ready()
    qe.step(q)
    before = read(qe.job(q, 0).file)
    rq.close(q["id"], "stuck", deps=qe.env.deps, queues_dir=qe.queues)
    with pytest.raises(rj.Refused, match="closed"):
        qe.step(q)
    assert read(qe.job(q, 0).file) == before and qe.status(q) == "CLOSED" and len(qe.calls) == 1
    qe.new()                                             # a closed queue no longer holds the repository


# ---- the command line -----------------------------------------------------------------------------------------------

def test_the_commands_go_status_and_close_work_from_the_command_line(qe, capsys):
    sys.path.insert(0, str(tr.ROOT / "scripts"))
    import argus
    base = ["--jobs-dir", str(qe.jobs), "--queues-dir", str(qe.queues), "queue"]
    q = qe.new()
    assert argus.main([*base, "status", q["id"]], deps=qe.env.deps) == 0 and "PENDING" in capsys.readouterr().out
    assert argus.main([*base, "go", q["id"], "--sha", rq.list_sha(q)[:12]], deps=qe.env.deps) == 0
    assert qe.q(q)["approved"] and "WAITING" in capsys.readouterr().out
    assert argus.main([*base, "close", q["id"], "--note", "done with it"], deps=qe.env.deps) == 0
    assert qe.status(q) == "CLOSED"
    assert argus.main([*base, "go", q["id"], "--sha", "0" * 12], deps=qe.env.deps) == 2


# ---- Fable's review of the diff -------------------------------------------------------------------------------------------

def test_a_step_on_another_jobs_directory_starts_nothing_and_forgets_nothing(qe, tmp_path):
    q = qe.ready(n=1, max_usd=1.0)
    qe.step(q)
    job = qe.q(q)["items"][0]["job"]
    with pytest.raises(rj.Refused, match="jobs directory"):
        rq.step(q["id"], cfg=qe.cfg, deps=qe.env.deps, queues_dir=qe.queues, jobs_dir=tmp_path / "elsewhere")
    assert qe.q(q)["items"][0]["job"] == job and len(qe.calls) == 1


def test_the_jobs_directory_is_part_of_what_the_human_approved(qe):
    q = qe.new()
    other = dict(q, jobs_dir="/somewhere/else")
    assert rq.list_sha(q) != rq.list_sha(other)


def test_a_stageless_new_job_of_another_issue_is_not_abandoned(qe):
    q = qe.ready()
    foreign = qe.env.code("jforeign")
    with foreign.lock():
        foreign.data["state"], foreign.data["stages"] = rj.NEW, {}
        foreign.save()
    data = qe.q(q)
    data["items"][0]["job"] = "jforeign"
    (qe.queues / q["id"] / "queue.json").write_text(json.dumps(data))
    assert "is not this queue's issue" in qe.step(q)
    assert qe.env.job("jforeign").data["state"] == rj.NEW and qe.q(q)["items"][0]["job"] == "jforeign"


def test_a_job_on_another_commit_is_not_the_items(qe):
    q = qe.ready()
    qe.step(q)
    job = qe.job(q, 0)
    with job.lock():
        job.data["inputs"]["commit"] = "b" * 40
        job.save()
    assert "is not this queue's issue" in qe.step(q)


def test_a_job_blocked_before_its_first_stage_stops_the_queue_instead_of_being_made_again(qe):
    q = qe.ready()
    qe.step(q)
    job = qe.job(q, 0)
    with job.lock():
        job.data["state"], job.data["stages"] = rj.BLOCKED, {}
        job.save()
    out = qe.step(q)
    assert "BLOCKED before its first stage" in out and qe.status(q) == "STOPPED" and len(qe.calls) == 1


def test_the_money_fits_exactly(qe):
    q = qe.ready(n=3, max_usd=3.0)
    for i in range(2):
        qe.step(q)
        qe.apply(q, i)
    qe.step(q)
    assert len(qe.calls) == 3 and qe.status(q) == "WAITING"      # two applied jobs hold what they spent: the third fits


def test_reordered_items_after_go_are_refused(qe):
    q = qe.ready()
    data = qe.q(q)
    data["items"][0], data["items"][1] = data["items"][1], data["items"][0]
    (qe.queues / q["id"] / "queue.json").write_text(json.dumps(data))
    with pytest.raises(rj.Refused, match="changed since"):
        qe.step(q)


def test_recovery_continues_through_step_not_only_status(qe):
    q = qe.ready()
    qe.step(q)
    qe.set_state(qe.job(q, 0), rj.AGENT_FAILED)
    assert "STOPPED" in qe.step(q)
    qe.set_state(qe.job(q, 0), rj.AWAITING_APPROVAL)
    assert "WAITING" in qe.step(q) and len(qe.calls) == 1


def test_an_unknown_queue_leaves_nothing_behind_and_an_id_is_matched_whole(qe):
    for bad in ("q20260101T000000Z-abcd", "q20260101T000000Z-abcd\n"):
        with pytest.raises(rj.Refused):
            rq.close(bad, "x", deps=qe.env.deps, queues_dir=qe.queues)
    assert not list(qe.queues.glob("*")) if qe.queues.exists() else True


def test_a_damaged_queue_file_is_refused_not_a_traceback(qe):
    q = qe.ready()
    data = qe.q(q)
    data["max_usd"] = "3"
    (qe.queues / q["id"] / "queue.json").write_text(json.dumps(data))
    with pytest.raises(rj.Refused, match="damaged"):
        qe.step(q)


def test_a_second_step_while_one_runs_is_refused_and_starts_nothing(qe):
    import fcntl
    q = qe.ready()
    fd = os.open(qe.queues / q["id"] / ".lock", os.O_RDWR)
    fcntl.flock(fd, fcntl.LOCK_EX)
    try:
        with pytest.raises(rj.Refused, match="in use"):
            qe.step(q)
    finally:
        os.close(fd)
    assert qe.calls == []


def test_an_item_records_when_its_job_was_started(qe):
    q = qe.ready()
    qe.step(q)
    assert qe.q(q)["items"][0]["at"] == "2026-10-23T00:00:00Z"


def test_a_job_the_human_abandoned_before_its_first_stage_is_made_again_by_the_next_step(tmp_path, monkeypatch):
    answer = [False]
    qe = Q(tmp_path, monkeypatch, confirm=lambda text: answer[0])
    q = qe.ready()
    with pytest.raises(rj.Refused):
        qe.step(q)
    stuck = qe.q(q)["items"][0]["job"]
    rj.abandon(stuck, "by hand", deps=qe.env.deps, jobs_dir=qe.jobs)
    answer[0] = True
    qe.step(q)
    assert qe.q(q)["items"][0]["job"] != stuck and qe.job(q, 0).data["state"] == rj.AWAITING_APPROVAL


@pytest.mark.parametrize("text,code", [("queue q STOPPED on demo (1 issues)", 1), ("queue q WAITING on demo (1 issues)", 0)])
def test_queue_step_exits_1_when_the_queue_is_stopped(qe, monkeypatch, text, code):
    sys.path.insert(0, str(tr.ROOT / "scripts"))
    import argus
    monkeypatch.setattr(rq, "step", lambda *a, **k: text)
    assert argus.main(["--jobs-dir", str(qe.jobs), "--queues-dir", str(qe.queues), "queue", "step", "q20260101T000000Z-abcd"], deps=qe.env.deps) == code


@pytest.mark.parametrize("field,value", [("issue", "another issue entirely"), ("repo", "/somewhere/else"), ("commit", "c" * 40)])
def test_a_started_job_that_differs_in_issue_repository_or_commit_is_not_the_items(qe, field, value):
    q = qe.ready()
    qe.step(q)
    job = qe.job(q, 0)
    with job.lock():
        job.data["inputs"][field] = value
        job.save()
    assert "is not this queue's issue" in qe.step(q) and len(qe.calls) == 1


def test_a_forgotten_id_is_saved_even_when_the_queue_then_stops(qe):
    q = qe.ready()
    data = qe.q(q)
    data["items"][0]["job"] = "j20260101_000000_dead"
    (qe.queues / q["id"] / "queue.json").write_text(json.dumps(data))
    git(qe.repo, "commit", "-q", "--allow-empty", "-m", "someone else")          # HEAD moved: nothing starts after the forgetting
    assert "HEAD moved" in qe.step(q)
    assert qe.q(q)["items"][0]["job"] is None and qe.calls == []


# ---- queue retry (2026-11-19): a rejected item gets a new job whose drafter is handed the patch readers' findings ---------------------------------

from router import patch_read as pr  # noqa: E402


def reject_on_findings(qe, q, i, notes=(("argus:hy4", "web.py: TRACE still gives 501"), ("argus:ds", "isdigit passes a unicode digit that int() refuses"))):
    """The item's job rejected, with an agent stage whose patch carries a `concerns` note (both readers' findings)."""
    job = qe.job(q, i)
    sha = "ab" * 32
    with job.lock():
        job.data["stages"]["a1"] = {"kind": "agent", "status": "DONE", "usd": 0.02, "run_id": f"{job.id}-a1", "review": {"patch_sha256": sha, "dir": "/x"}}
        job.save()
    first, second = notes
    rec = {"key": pr.key("a1", sha), "sid": "a1", "patch_sha256": sha, "verdict": "concerns", "note": first[1], "at": "2026-11-19T10:00:00Z",
           "reader": {"kind": "argus", "id": first[0]}, "template_sha256": pr.TEMPLATE_SHA256,
           "second": {"verdict": "concerns", "note": second[1], "at": "2026-11-19T10:01:00Z", "reader": {"kind": "argus", "id": second[0]}, "template_sha256": pr.TEMPLATE_SHA256}}
    (job.dir / "patch_read_a1.json").write_text(json.dumps(rec))
    qe.set_state(job, rj.REJECTED)
    return job


def retry(qe, q, n=1, **kw):
    return rq.retry(q["id"], n, deps=qe.env.deps, queues_dir=qe.queues, jobs_dir=qe.jobs, **kw)


def test_a_rejected_item_is_retried_with_both_readers_findings_handed_to_the_new_drafter_as_data(qe):
    q = qe.ready()
    qe.step(q)
    old = reject_on_findings(qe, q, 0)
    assert qe.status(q) == "STOPPED" and "argus queue retry" in rq.status_lines(qe.q(q), jobs_dir=qe.jobs)
    got = retry(qe, q)
    item = got["items"][0]
    assert item["job"] is None and "TRACE still gives 501" in item["retry_note"] and "isdigit passes" in item["retry_note"]
    assert item["retries"][0]["job"] == old.id and item["retries"][0]["spent_nano"] > 0 and qe.status(q) == "WAITING"
    qe.step(q)
    new = qe.job(q, 0)
    assert new.id != old.id and new.data["inputs"]["issue"] == old.data["inputs"]["issue"]          # the same issue, byte for byte
    assert qe.calls[-1]["note"] == item["retry_note"] and qe.calls[-1]["note_by"] == "reader"
    st = new.data["stages"]["d1"]
    assert st["note"] == item["retry_note"] and st["note_by"] == "reader" and new.data.get("reader_steered") and not new.data.get("human_steered")
    assert rj.open_job(old.id, qe.jobs).data["state"] == rj.REJECTED                               # the rejected job is untouched


def test_what_the_retired_attempt_spent_stays_counted_in_the_queues_money(qe):
    q = qe.ready(n=2, max_usd=2.0)
    qe.step(q)
    old = reject_on_findings(qe, q, 0)
    retry(qe, q)
    qe.step(q)
    st = qe.q(q)
    spent = st["items"][0]["retries"][0]["spent_nano"]
    status, detail, *_ = rq.derive(st)
    assert spent > 0 and rj.spent_nano(old) == spent
    assert rq.retired_nano(st) == spent and spent > 0
    assert status == rq.WAITING and "the money" not in detail and qe.job(q, 0).data["state"] == rj.AWAITING_APPROVAL    # two items, $2.00: the new job started beside what was spent


def test_a_retired_attempt_counts_what_it_spent_NOW_not_what_it_had_spent_when_it_was_retried(qe, monkeypatch):
    q = qe.ready()
    qe.step(q)
    old = reject_on_findings(qe, q, 0)
    retry(qe, q)
    st = qe.q(q)
    real = rj.spent_nano
    monkeypatch.setattr(rq.rj, "spent_nano", lambda job: 777_000_000 if job.id == old.id else real(job))
    assert rq.retired_nano(st) == 777_000_000
    st["items"][0]["retries"][0]["job"] = "j20200101_000000_dead"                                     # a job that cannot be opened: the recorded number
    assert rq.retired_nano(st) == st["items"][0]["retries"][0]["spent_nano"]


@pytest.mark.parametrize("bad", [{"retries": [{"job": "j1", "spent_nano": -5, "findings": "x"}]}, {"retries": [{"job": "j1", "spent_nano": None, "findings": "x"}]},
                                 {"retries": [{"job": "j1", "spent_nano": True, "findings": "x"}]}, {"retries": "x"},
                                 {"retries": [{"job": "j1", "spent_nano": 1, "findings": "x"}] * 3}, {"retry_note": 5}, {"retry_note": "x" * 3001}])
def test_a_queue_json_with_bad_retry_fields_is_damaged_not_a_traceback_or_a_bypass(qe, bad):
    q = qe.ready()
    st = qe.q(q)
    st["items"][0].update(bad)
    assert rq.shape_ok(st, q["id"]) is False
    (qe.queues / q["id"] / "queue.json").write_text(json.dumps(st))
    with pytest.raises(rq.Refused, match="damaged"):
        rq.status(q["id"], queues_dir=qe.queues, jobs_dir=qe.jobs)
    with pytest.raises(rq.Refused, match="damaged"):
        qe.step(q)


def test_a_step_on_an_item_that_was_never_retried_hands_no_note_and_marks_nothing(qe):
    q = qe.ready()
    qe.step(q)
    assert "note" not in qe.calls[0] and "note_by" not in qe.calls[0]
    assert not qe.job(q, 0).data.get("reader_steered") and not qe.job(q, 0).data.get("human_steered")
    assert "reader-steered" not in rj.status(qe.job(q, 0).id, jobs_dir=qe.jobs)


def test_the_new_job_of_a_retry_says_in_its_status_that_the_readers_findings_steered_its_draft(qe):
    q = qe.ready()
    qe.step(q)
    reject_on_findings(qe, q, 0)
    retry(qe, q)
    qe.step(q)
    assert "reader-steered" in rj.status(qe.job(q, 0).id, jobs_dir=qe.jobs)


def test_a_retry_needs_an_approved_unchanged_list_and_the_queues_own_jobs_directory(qe, tmp_path):
    q = qe.new()
    with pytest.raises(rq.Refused, match="not approved"):
        retry(qe, q)
    q = qe.go(q)
    qe.step(q)
    reject_on_findings(qe, q, 0)
    with pytest.raises(rq.Refused, match="jobs directory"):
        rq.retry(q["id"], 1, deps=qe.env.deps, queues_dir=qe.queues, jobs_dir=tmp_path / "elsewhere")
    st = qe.q(q)
    st["max_usd"] = 4.0                                                                              # the list changed after go
    (qe.queues / q["id"] / "queue.json").write_text(json.dumps(st))
    with pytest.raises(rq.Refused, match="not approved|list changed"):
        retry(qe, q)


def test_the_new_job_of_a_retry_must_fit_the_queues_money_beside_what_the_old_attempt_spent(qe):
    q = qe.ready(n=1, max_usd=1.0)                                                                   # money for one job only
    qe.step(q)
    reject_on_findings(qe, q, 0)
    retry(qe, q)
    out = qe.step(q)
    assert "the money" in out and qe.status(q) == "STOPPED" and len(qe.calls) == 1


@pytest.mark.parametrize("what", ["not rejected", "no findings", "other item", "closed", "third retry"])
def test_a_retry_is_refused_unless_the_item_is_the_stopped_one_rejected_on_a_concerns_and_has_retries_left(qe, what):
    q = qe.ready()
    qe.step(q)
    if what == "not rejected":
        with pytest.raises(rq.Refused, match="stopped at"):
            retry(qe, q)
        return
    if what == "no findings":
        job = qe.job(q, 0)
        qe.set_state(job, rj.REJECTED)                                                               # rejected by hand: no reader note
        with pytest.raises(rq.Refused, match="nothing to hand"):
            retry(qe, q)
        return
    reject_on_findings(qe, q, 0)
    if what == "other item":
        with pytest.raises(rq.Refused, match="no item 5|stopped at"):
            retry(qe, q, 5)
        with pytest.raises(rq.Refused, match="stopped at"):
            retry(qe, q, 2)
    elif what == "closed":
        rq.close(q["id"], "stop", deps=qe.env.deps, queues_dir=qe.queues)
        with pytest.raises(rq.Refused, match="closed"):
            retry(qe, q)
    else:
        for _ in range(rq.MAX_RETRIES):
            retry(qe, q)
            qe.step(q)
            reject_on_findings(qe, q, 0)
        with pytest.raises(rq.Refused, match="retried 2 times"):
            retry(qe, q)
        assert "argus queue retry" not in rq.status_lines(qe.q(q), jobs_dir=qe.jobs)
    assert qe.q(q)["items"][1]["job"] is None


def test_the_findings_are_bounded_and_a_retry_changes_neither_the_approved_list_nor_the_issue_files(qe, monkeypatch):
    q = qe.ready()
    qe.step(q)
    reject_on_findings(qe, q, 0, notes=(("argus:a", "x" * (pr.NOTE_MAX - 5)), ("argus:b", "y" * (pr.NOTE_MAX - 5))))
    before = rq.list_sha(qe.q(q))
    monkeypatch.setattr(rq, "FINDINGS_MAX", 300)
    got = retry(qe, q)
    note = got["items"][0]["retry_note"]
    assert len(note) <= 300 and note.endswith("[cut]") and note.startswith("- [argus:a] xxx")
    assert rq.list_sha(got) == before and qe.status(q) == "WAITING"
    for i in range(1, 4):
        assert (qe.queues / q["id"] / f"issue-{i}.md").exists()


def test_the_findings_of_both_readers_fit_the_bound_as_they_are(qe):
    q = qe.ready()
    qe.step(q)
    reject_on_findings(qe, q, 0, notes=(("argus:a", "x" * (pr.NOTE_MAX - 5)), ("argus:b", "y" * (pr.NOTE_MAX - 5))))
    note = retry(qe, q)["items"][0]["retry_note"]
    assert "[cut]" not in note and "x" * 400 in note and "y" * 400 in note


def test_retry_works_from_the_command_line(qe, capsys):
    sys.path.insert(0, str(tr.ROOT / "scripts"))
    import argus
    q = qe.ready()
    qe.step(q)
    reject_on_findings(qe, q, 0)
    base = ["--jobs-dir", str(qe.jobs), "--queues-dir", str(qe.queues), "queue"]
    assert argus.main([*base, "retry", q["id"], "--item", "1"], deps=qe.env.deps) == 0
    assert "WAITING" in capsys.readouterr().out and qe.q(q)["items"][0]["retries"]
    assert argus.main([*base, "retry", q["id"], "--item", "1"], deps=qe.env.deps) == 2                # nothing to retry now


def test_a_retry_names_the_item_the_queue_stopped_at_not_another_item_that_happens_to_hold_a_rejected_job(qe):
    q = qe.ready(n=2, max_usd=2.0)
    qe.step(q)
    job = reject_on_findings(qe, q, 0)
    st = qe.q(q)
    st["items"][1]["job"] = job.id                                                                   # a hand-edited queue.json: item 2 points at the same rejected job
    (qe.queues / q["id"] / "queue.json").write_text(json.dumps(st))
    with pytest.raises(rq.Refused, match="stopped at"):
        retry(qe, q, 2)
    assert "retries" not in qe.q(q)["items"][1]


def test_a_retry_hands_the_drafter_only_the_blocker_findings_never_the_nits(qe):
    q = qe.ready(n=1, max_usd=3.0)
    qe.step(q)
    job = reject_on_findings(qe, q, 0, notes=(("argus:hy4", "it deletes the parent directory"), ("argus:ds", "year 0-99 is accepted")))
    f = job.dir / "patch_read_a1.json"
    rec = json.loads(f.read_text())
    rec["severity"] = "blocker"
    rec["second"]["severity"] = "nit"
    f.write_text(json.dumps(rec))
    out = retry(qe, q)
    note = qe.q(q)["items"][0]["retry_note"]
    assert "deletes the parent directory" in note and "year 0-99" not in note
