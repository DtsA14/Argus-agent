"""SPEC_KARTU_SETUJU section 5 rev 2 (PR 5a of T3): `argus apply` of a job that is an item of a queue made from a PRD folder needs a fresh `ok` note of the domain
reader, bound through the chain queue -> PRD folder -> item issue -> digest of the examples -> note. Jobs that are not items of such a queue are not asked.
`argus apply` and the install card (PR 5b) use the same `examples_read.chain`."""
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import test_router as tr  # noqa: E402
from patch_read_util import read_ok  # noqa: E402
from test_approve_plan import with_tree  # noqa: E402
from test_chat_cards import AFTER, PJOB, SAME, issue_text, stored_for, write_prd  # noqa: E402
from test_example_gate import issue_with, review_ready, start  # noqa: E402,F401
from router import apply as ra  # noqa: E402
from router import examples_read as er  # noqa: E402
from router import job as rj  # noqa: E402

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="posix")
QID = "q20261117T100400Z-abcd"


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    h.mkdir()
    (h / ".gitconfig").write_text("[user]\n\tname = Global Person\n\temail = global@example.org\n")
    monkeypatch.setenv("HOME", str(h))
    for k in [k for k in os.environ if k.startswith("GIT_")]:
        monkeypatch.delenv(k)


@pytest.fixture
def world(tmp_path):
    """A code job `jtest` ready to apply, whose issue has the examples SAME and AFTER; a PRD job with the same examples in its item 1; a queue made from
    that PRD folder whose item 1 is `jtest`."""
    env = tr.Env(tmp_path)
    review_ready(env, SAME, AFTER)
    env.queues = tmp_path / "queues"
    env.queues.mkdir()
    prd_dir, files = write_prd(env.jobs, [issue_text(SAME, AFTER)], [stored_for([SAME, AFTER])])
    with_tree(prd_dir)
    (prd_dir / "runs" / f"{PJOB}-w1" / "source" / "README.md").write_text("The floor of a total is 0.\n")
    env.prd_dir, env.prd_files = prd_dir, files
    env.qdir = write_queue(env)
    return env


def write_queue(env, **kw):
    d = env.queues / QID
    d.mkdir(exist_ok=True)
    issue = (env.prd_dir / "prd-w1" / "issue-1.md").read_bytes()
    q = {"id": QID, "repo": "/secret/path", "name": "athena", "base_commit": "c" * 40, "jobs_dir": str(env.jobs), "max_usd": 2.0, "job_cap_usd": 0.5,
         "environment": "athena_py312", "items": [{"n": 1, "issue_sha256": hashlib.sha256(issue).hexdigest(), "job": "jtest"}],
         "prd": {"sha": json.loads((env.prd_dir / "job.json").read_text())["prd_turns"][-1]["folder_sha"], "dir": str(env.prd_dir / "prd-w1")}}
    q.update(kw)
    (d / "queue.json").write_text(json.dumps(q))
    return d


def edit_queue(env, fn):
    f = env.qdir / "queue.json"
    q = json.loads(f.read_text())
    fn(q)
    f.write_text(json.dumps(q))


def note(env, verdict="ok", sources=("permintaan Atha",), text="fits"):
    _, info = er.bundle(env.jobs, PJOB, 1)
    return er.record(PJOB, 1, verdict, info["bundle_sha256"], "opus-1", list(sources), text, deps=env.deps, jobs_dir=env.jobs)


def apply(env, **kw):
    job = env.job()
    sha = hashlib.sha256((Path(job.data["stages"]["a1"]["review"]["dir"]) / "changes.patch").read_bytes()).hexdigest()
    read_ok(env, sha)
    return ra.apply("jtest", sha[:12], deps=env.deps, jobs_dir=env.jobs, queues_dir=env.queues, **kw)


def head(env):
    import subprocess
    return subprocess.run(["git", "-C", str(env.repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()


def refused(env, match):
    before = head(env)
    with pytest.raises(rj.Refused, match=match):
        apply(env)
    assert head(env) == before and env.job().data["state"] == rj.REVIEW_READY


# ---- the gate -----------------------------------------------------------------------------------------------------------------

def test_apply_of_a_queue_item_refuses_without_a_note_and_says_how_to_write_one(world):
    refused(world, f"no domain reader's note.*examples-read {PJOB} --item 1 --bundle")


def test_apply_refuses_when_the_reader_has_concerns(world):
    note(world, verdict="concerns", sources=("hanya tulisan penulis",), text="the 3% is only in the PRD")
    refused(world, "recorded concerns")


def test_apply_with_a_fresh_ok_note_applies(world):
    note(world)
    assert apply(world).data["state"] == rj.APPLIED


def test_apply_refuses_a_note_that_went_stale(world):
    note(world)
    (world.prd_dir / "runs" / f"{PJOB}-w1" / "source" / "README.md").write_text("The floor is 5.\n")
    refused(world, "stale")


def test_apply_refuses_a_damaged_note(world):
    note(world)
    (world.prd_dir / "examples_read_w1.json").write_text("{")
    refused(world, "cannot be read")


@pytest.mark.parametrize("change,why", [
    (lambda q: q["prd"].update(sha="9" * 64), "not the one this queue was made from"),
    (lambda q: q["items"][0].update(issue_sha256="9" * 64), "not the issue of the queue item"),
    (lambda q: q["prd"].update(dir=q["prd"]["dir"].replace("prd-w1", "prd-w9")), "not the one this queue was made from|cannot be read"),
    (lambda q: q["prd"].update(dir="/elsewhere/j20261117_100000_aaaa/prd-w1"), "not in this jobs directory"),
])
def test_a_break_in_the_chain_refuses_even_with_a_good_note(world, change, why):
    note(world)
    edit_queue(world, change)
    refused(world, why)


def test_examples_that_are_not_the_ones_the_prd_item_had_refuse(world):
    note(world)
    job = world.job()
    with job.lock():
        job.data["inputs"]["issue"] = issue_with(SAME)                                    # one example fewer than the PRD item
        job.save()
    refused(world, "digest|examples of the job's issue|not the examples|examples failed|issue")


def test_a_job_in_two_queues_is_refused(world):
    note(world)
    d2 = world.queues / "q20261117T100500Z-abce"
    shutil.copytree(world.qdir, d2)
    (d2 / "queue.json").write_text((d2 / "queue.json").read_text().replace(QID, "q20261117T100500Z-abce"))
    refused(world, "more than one queue")


def test_a_queue_of_another_jobs_directory_does_not_count(world):
    edit_queue(world, lambda q: q.update(jobs_dir="/some/other/jobs"))
    assert apply(world).data["state"] == rj.APPLIED                                       # not an item of a queue of this jobs directory


# ---- who is not asked ----------------------------------------------------------------------------------------------------------

def test_a_job_that_is_not_in_any_queue_is_not_asked(world):
    shutil.rmtree(world.qdir)
    assert er.chain(world.job(), world.jobs, world.queues)["applicable"] is False
    assert apply(world).data["state"] == rj.APPLIED


def test_a_queue_without_a_prd_is_not_asked(world):
    edit_queue(world, lambda q: q.pop("prd"))
    res = er.chain(world.job(), world.jobs, world.queues)
    assert res["applicable"] is False and res["ok"] is True
    assert apply(world).data["state"] == rj.APPLIED


def test_a_job_whose_issue_has_no_examples_is_not_asked(tmp_path):
    env = tr.Env(tmp_path)
    start(env, issue_with(SAME))
    env.approve()
    job = env.job()
    with job.lock():
        job.data["inputs"]["issue"] = "an issue without any block"
        job.save()
    res = er.chain(env.job(), env.jobs, tmp_path / "queues")
    assert res == {"applicable": False, "ok": True, "kind": "tidak_berlaku", "why": "the issue has no examples", "rec": None, "prd_job": None, "item": None}


def test_a_missing_queues_directory_is_not_a_queue(world):
    shutil.rmtree(world.queues)
    res = er.chain(world.job(), world.jobs, world.queues)
    assert res["applicable"] is False and "no queues directory" in res["why"]


def test_a_damaged_queue_file_is_skipped_not_read_as_a_match(world):
    note(world)
    (world.qdir / "queue.json").write_text("{")
    assert er.chain(world.job(), world.jobs, world.queues)["applicable"] is False


# ---- chain(): what the install card reads ---------------------------------------------------------------------------------------

def test_chain_gives_the_whole_picture_for_a_queue_item(world):
    res = er.chain(world.job(), world.jobs, world.queues)
    assert res["applicable"] and not res["ok"] and res["kind"] == "none" and res["prd_job"] == PJOB and res["item"] == 1 and res["rec"] is None
    note(world)
    res = er.chain(world.job(), world.jobs, world.queues)
    assert res["ok"] is True and res["kind"] == "ok" and res["rec"]["verdict"] == "ok" and res["why"] is None
    note(world, verdict="concerns", sources=("hanya tulisan penulis",), text="x")
    res = er.chain(world.job(), world.jobs, world.queues)
    assert res["ok"] is False and res["kind"] == "concerns" and res["rec"]["note"] == "x"


def test_chain_writes_nothing_and_starts_nothing(world, monkeypatch):
    import subprocess
    note(world)
    for name in ("Popen", "run", "call", "check_output"):
        monkeypatch.setattr(subprocess, name, lambda *a, **k: (_ for _ in ()).throw(AssertionError("a process")))

    def snap():
        return sorted((str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in list(world.jobs.rglob("*")) + list(world.queues.rglob("*")))
    before = snap()
    er.chain(world.job(), world.jobs, world.queues)
    assert snap() == before


def test_the_order_of_the_refusals_keeps_the_patch_read_first(world):
    note(world)
    job = world.job()
    sha = hashlib.sha256((Path(job.data["stages"]["a1"]["review"]["dir"]) / "changes.patch").read_bytes()).hexdigest()
    with pytest.raises(rj.Refused, match="patch-read"):
        ra.apply("jtest", sha[:12], deps=world.deps, jobs_dir=world.jobs, queues_dir=world.queues)       # no patch-read note yet


def test_a_second_call_that_heals_a_crash_still_needs_the_note(world, monkeypatch):
    note(world)
    monkeypatch.setattr(rj, "_record_applied", lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt))
    with pytest.raises(KeyboardInterrupt):
        apply(world)
    monkeypatch.undo()
    os.remove(world.prd_dir / "examples_read_w1.json")
    with pytest.raises(rj.Refused, match="no domain reader's note"):
        apply(world)


def test_the_cli_passes_the_queues_directory(world, capsys):
    import argus
    note(world)
    job = world.job()
    sha = hashlib.sha256((Path(job.data["stages"]["a1"]["review"]["dir"]) / "changes.patch").read_bytes()).hexdigest()
    read_ok(world, sha)
    base = ["--jobs-dir", str(world.jobs), "--queues-dir", str(world.queues)]
    assert argus.main([*base, "apply", "jtest", "--read-sha", sha[:12]], deps=world.deps) == 0
    assert world.job().data["state"] == rj.APPLIED


def test_the_cli_refuses_a_queue_item_without_a_note(world, capsys):
    import argus
    job = world.job()
    sha = hashlib.sha256((Path(job.data["stages"]["a1"]["review"]["dir"]) / "changes.patch").read_bytes()).hexdigest()
    read_ok(world, sha)
    base = ["--jobs-dir", str(world.jobs), "--queues-dir", str(world.queues)]
    assert argus.main([*base, "apply", "jtest", "--read-sha", sha[:12]], deps=world.deps) != 0
    assert "no domain reader's note" in capsys.readouterr().err and world.job().data["state"] == rj.REVIEW_READY
