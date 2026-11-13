"""SPEC_REPRO_PATCHED: the issue's example run again on the patched tree, shown next to the base run; display only."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_drafter as td  # noqa: E402
from acceptance import repro as rp  # noqa: E402
from router import job as rj  # noqa: E402
from test_repro import BAD, OK, Box, code_with, issue  # noqa: E402
from test_router import failed_a1, retry  # noqa: E402

PATCHED_OK = {"exit_code": 0, "stdout": "0o644\n", "stderr": "", "timed_out": False}
RAISED_VALUE = {"exit_code": 1, "stdout": "", "stderr": "Traceback\nValueError: nope\n", "timed_out": False}


def pfile(job, sid="a1"):
    return job.dir / f"repro_patched_{sid}.json"


class Seen:
    """A sandbox stand-in that answers from a list and keeps what the tree looked like when the code ran."""
    def __init__(self, *answers):
        self.answers, self.calls, self.trees = list(answers), [], []

    def __call__(self, code, *, workdir, data_dir, cfg, **kw):
        self.calls.append(Path(workdir))
        shop = Path(workdir) / "src" / "shop.py"
        self.trees.append(shop.read_text() if shop.exists() else None)
        a = self.answers.pop(0)
        if isinstance(a, BaseException):
            raise a
        return a


# ---- the label: compared both ways, from status, exception type and last output --------------------------------------

def res(status, out="", err="", index=0):
    return {"index": index, "status": status, "exit_code": 0 if status == "ok" else 1, "stdout": out,
            "stderr_last_line": err, "reason": ""}


def test_the_label_is_changed_in_both_directions_and_unchanged_when_nothing_differs():
    assert rp.label([res("raised", err="ValueError: x")], [res("ok", "0o644\n")]) == ["changed"]
    assert rp.label([res("ok", "1\n")], [res("raised", err="ValueError: x")]) == ["changed"]       # #1257: the fix raises
    assert rp.label([res("ok", "0o600\n")], [res("ok", "0o600\n")]) == ["unchanged"]
    assert rp.label([res("raised", err="ValueError: a")], [res("raised", err="ValueError: b")]) == ["unchanged"]
    assert rp.label([res("raised", err="ValueError: a")], [res("raised", err="KeyError: a")]) == ["changed"]
    assert rp.label([res("ok", "1\n")], [res("ok", "1\n2\n")]) == ["changed"]


def test_a_block_with_no_run_on_either_side_gets_no_label():
    skipped = {"index": 0, "status": "skipped", "exit_code": None, "stdout": "", "stderr_last_line": "", "reason": "x"}
    assert rp.label([skipped], [res("ok")]) == [None]
    assert rp.label([res("ok")], [skipped]) == [None]
    assert rp.label(None, [res("ok")]) == [None]
    assert rp.label([res("ok")], []) == [None]


# ---- in the job: when it runs, on what, what it shows -----------------------------------------------------------------

def run_to_review(tmp_path, monkeypatch, *answers, **kw):
    box = Seen(*answers)
    env, job = code_with(tmp_path, monkeypatch, box, **kw)
    job, r = env.approve()
    return env, job, box, r


def test_the_example_runs_on_the_patched_tree_after_review_ready_is_saved(tmp_path, monkeypatch):
    seen_state = []

    class Spy(Seen):
        def __call__(self, code, **kw):
            seen_state.append(rj.open_job("jtest", env_jobs[0]).data["state"] if env_jobs else None)
            return super().__call__(code, **kw)
    env_jobs = []
    box = Spy(RAISED_VALUE, PATCHED_OK)
    env, job = code_with(tmp_path, monkeypatch, box)
    env_jobs.append(env.jobs)
    seen_state.clear()
    job, r = env.approve()
    assert job.data["state"] == rj.REVIEW_READY
    assert seen_state == [rj.REVIEW_READY]                       # the status was saved before the run
    assert len(box.calls) == 2 and box.trees[0] == td.BUGGY and box.trees[1] == td.FIXED    # base, then base + patch
    rec = json.loads(pfile(job).read_text())
    assert rec["results"][0]["status"] == "ok" and rec["results"][0]["stdout"] == "0o644\n"


def test_status_shows_both_runs_and_the_label_and_a_neutral_sentence(tmp_path, monkeypatch):
    env, job, box, _ = run_to_review(tmp_path, monkeypatch, RAISED_VALUE, PATCHED_OK)
    text = rj.status("jtest", jobs_dir=env.jobs)
    assert 'issue example, base -> patched: raised ValueError: nope -> ran clean "0o644" [changed]' in text
    assert "the example runs agent-written code; compare both outputs against the issue" in text
    assert "does not prove the bug is fixed" not in text


def test_an_unchanged_example_is_labelled_unchanged(tmp_path, monkeypatch):
    env, job, box, _ = run_to_review(tmp_path, monkeypatch, OK, OK)
    assert "[unchanged]" in rj.status("jtest", jobs_dir=env.jobs)


def test_an_invalid_package_is_not_run_and_says_why(tmp_path, monkeypatch):
    from codetask import review
    monkeypatch.setattr(review, "build", lambda *a, **kw: {"valid": False, "problems": ["x"], "dir": tmp_path})
    box = Seen(OK)
    env, job = code_with(tmp_path, monkeypatch, box)
    job, _ = env.approve()
    assert job.data["state"] == rj.REVIEW_INVALID and len(box.calls) == 1        # only the base run
    assert json.loads(pfile(job).read_text()).get("skipped") == "review package invalid"
    assert "issue example, base -> patched: not run (review package invalid)" in rj.status("jtest", jobs_dir=env.jobs)


def test_a_failing_run_leaves_the_job_review_ready_and_says_error(tmp_path, monkeypatch):
    env, job, box, r = run_to_review(tmp_path, monkeypatch, OK, RuntimeError("docker is down"))
    assert r["status"] == "DONE" and job.data["state"] == rj.REVIEW_READY
    assert "issue example, base -> patched: not run (error)" in rj.status("jtest", jobs_dir=env.jobs)


def test_a_run_that_raises_inside_repro_is_swallowed(tmp_path, monkeypatch):
    def boom(*a, **kw):
        raise ValueError("odd")
    monkeypatch.setattr(rp, "run_patched", boom)
    env, job = code_with(tmp_path, monkeypatch, Seen(OK))
    job, r = env.approve()
    assert job.data["state"] == rj.REVIEW_READY
    assert "not run (error)" in rj.status("jtest", jobs_dir=env.jobs)


class Died(BaseException):
    """The process dies in the middle of the run."""


def test_dying_during_the_run_leaves_a_review_ready_job_and_resume_does_not_rerun_the_agent(tmp_path, monkeypatch):
    box = Seen(OK, Died())
    env, job = code_with(tmp_path, monkeypatch, box)
    with pytest.raises(Died):
        env.approve()
    job = env.job()
    assert job.data["state"] == rj.REVIEW_READY
    calls = len(env.coder.calls)
    assert "not run (error)" in rj.status("jtest", jobs_dir=env.jobs)           # no half-written file reads as a result
    try:
        rj.resume("jtest", cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs)
    except rj.Refused:
        pass
    assert len(env.coder.calls) == calls and env.job().data["state"] == rj.REVIEW_READY


def test_three_not_run_states_read_differently_and_a_job_from_before_has_no_line(tmp_path, monkeypatch):
    env, job, box, _ = run_to_review(tmp_path, monkeypatch, OK, PATCHED_OK)
    ok_text = rj.status("jtest", jobs_dir=env.jobs)
    assert "base -> patched" in ok_text
    pfile(job).unlink()                                                       # a job made before this existed
    assert "base -> patched" not in rj.status("jtest", jobs_dir=env.jobs)


# ---- what the result can never do ----------------------------------------------------------------------------------

def test_the_result_never_changes_the_job(tmp_path, monkeypatch):
    seen = []
    for i, answer in enumerate((PATCHED_OK, RAISED_VALUE, {"exit_code": None, "stdout": "", "stderr": "", "timed_out": True},
                                RuntimeError("down"))):
        env, job, box, r = run_to_review(tmp_path / f"t{i}", monkeypatch, OK, answer)
        d = job.data
        patch = (Path(d["stages"]["a1"]["review"]["dir"]) / "changes.patch").read_bytes()
        seen.append((d["state"], r["status"], d["stages"]["a1"]["usd"], patch,
                     [e["what"] for e in d["log"] if e["what"] != "repro_patched"]))
    assert all(s == seen[0] for s in seen)


def test_the_line_is_checked_against_the_patch_on_disk(tmp_path, monkeypatch):
    env, job, box, _ = run_to_review(tmp_path, monkeypatch, OK, PATCHED_OK)
    patch = Path(job.data["stages"]["a1"]["review"]["dir"]) / "changes.patch"
    patch.write_bytes(patch.read_bytes() + b"\n")
    text = rj.status("jtest", jobs_dir=env.jobs)
    assert "not run (the patch changed since it was run)" in text and "base -> patched: ran clean" not in text


def test_output_is_cut_and_cleaned_again_when_read_back(tmp_path, monkeypatch):
    env, job, box, _ = run_to_review(tmp_path, monkeypatch, OK, {**PATCHED_OK, "stdout": "a" * 5000})
    assert len(json.loads(pfile(job).read_text())["results"][0]["stdout"].encode()) <= rp.MAX_OUT
    rec = json.loads(pfile(job).read_text())
    rec["results"][0]["stdout"] = "x\x1b[2Jy"
    pfile(job).write_text(json.dumps(rec))
    assert "\x1b" not in rj.status("jtest", jobs_dir=env.jobs)


def test_the_judge_is_never_called_from_the_job_steps(tmp_path, monkeypatch):
    from codetask import judge as jd

    def judged(*a, **kw):
        raise AssertionError("the judge must not run by itself")
    monkeypatch.setattr(jd, "run_judge", judged)
    env, job, box, r = run_to_review(tmp_path, monkeypatch, OK, PATCHED_OK)
    assert r["status"] == "DONE"


# ---- two stages: status shows the one whose package is being reviewed ------------------------------------------------

def test_status_shows_the_file_of_the_stage_under_review(tmp_path, monkeypatch):
    from test_router import Env
    monkeypatch.setattr("tools.sandbox.run_python", Seen(OK, PATCHED_OK))
    monkeypatch.setattr(td, "ISSUE", td.ISSUE + "\n\n" + issue("print(1)"))
    env = Env(tmp_path)
    job = failed_a1(env, monkeypatch)
    pfile(job, "a1").write_text(json.dumps({"key": "x", "skipped": None, "results": [res("ok", "STAGE-A1\n")]}))
    job, r = retry(env)
    assert r["status"] == "DONE" and "a2" in job.data["stages"]
    text = rj.status("jtest", jobs_dir=env.jobs)
    assert "STAGE-A1" not in text and "base -> patched: " in text
