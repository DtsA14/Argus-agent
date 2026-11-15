"""SPEC_PRD_QUEUE part A: `argus queue` (router/queue.py): issues in order on one repository, each on the commit the one before was
applied as; the human approves the list and the money once; `step` makes at most one drafter run and never approves or applies;
a failure stops the queue; the money of the started jobs, at their caps, never passes max_usd."""
import json
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

@pytest.mark.parametrize("state,counts_cap", [(rj.APPLIED, True), (rj.REJECTED, True), (rj.DRAFT_FAILED, True), (rj.AGENT_FAILED, True),
                                              (rj.AWAITING_APPROVAL, True), (rj.ABANDONED, False), (rj.BLOCKED, False), (rj.REVIEW_INVALID, False)])
def test_a_job_holds_its_whole_cap_unless_it_cannot_spend_again(qe, state, counts_cap):
    q = qe.ready()
    qe.step(q)
    job = qe.job(q, 0)
    qe.set_state(job, state)
    assert rq.committed_nano(qe.job(q, 0)) == (1_000_000_000 if counts_cap else rj.spent_nano(qe.job(q, 0)))
    assert counts_cap or rj.spent_nano(qe.job(q, 0)) > 0          # the fake drafter spent something: "spent" and "zero" differ


def test_the_started_jobs_at_their_caps_never_pass_the_queue_money(qe):
    q = qe.ready(n=3, max_usd=2.0)
    for i in range(2):
        qe.step(q)
        qe.apply(q, i)
    out = qe.step(q)                                     # two APPLIED jobs hold $2.00 each at cap: a judge could still spend on them
    assert qe.status(q) == "STOPPED" and "the money" in out and len(qe.calls) == 2


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
    assert len(qe.calls) == 3 and qe.status(q) == "WAITING"      # 1 + 1 held, 1 more fits at exactly $3.00


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
