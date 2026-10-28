"""SPEC_DRAFTER_SUBMIT_STEPS (from the 21379 re-run): the drafter's steps for reading end at max_steps, its submits do
not. After max_steps, steps that offer only SubmitDraft and ReviseDraft follow until max_submits is used up; a reply
without a submit there ends the run."""
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_drafter as td  # noqa: E402
from test_drafter import root  # noqa: E402,F401  (the fixture)

from codetask import drafter as dt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BAD = td.args_with(td.GREEN_TEST)                       # its new test passes on the baseline: rejected
FIX = {"new_tests": td.ARGS["new_tests"]}


def texts(model, n):
    return [m.content for m in model.calls[n]["messages"] if isinstance(m.content, str)]


def test_a_rejection_on_the_last_reading_step_can_still_be_fixed(root, tmp_path):  # noqa: F811
    """The 21379 re-run's d3: read to the end, a rejection with one problem left, no step to fix it."""
    script = [td.READ, td.call("SubmitDraft", BAD, "s1"), td.call("ReviseDraft", {"unverifiable": []}, "v1"),
              td.call("ReviseDraft", FIX, "v2")]
    r, model, d = td.run(root, tmp_path, script, config=td.cfg(max_steps=3))
    assert r["status"] == dt.DRAFTED and len(model.calls) == 4
    res = json.loads((d / "result.json").read_text())
    assert res["drafting"]["submits"] == 3 and res["drafting"]["steps"] == 3       # the accepting submit: step 3
    note = dt.SUBMIT_STEPS_NOTE.format(n=3)
    assert note in texts(model, 3) and note not in "\n".join(texts(model, 2))


def test_the_submit_steps_end_when_the_submits_are_used_up(root, tmp_path):  # noqa: F811
    script = [td.READ] + [td.call("SubmitDraft", BAD, "s1")] + [td.call("ReviseDraft", {}, f"v{i}") for i in range(3)]
    r, model, d = td.run(root, tmp_path, script, config=td.cfg(max_steps=2, max_submits=3))
    assert r["status"] == dt.NO_DRAFT and r["stop_reason"] == "max_steps" and len(model.calls) == 4
    res = json.loads((d / "result.json").read_text())["drafting"]
    assert res["submits"] == 3 and res["steps"] == 4 and res["end"] == "max_steps"


def test_a_reply_without_a_submit_in_a_submit_step_ends_the_run(root, tmp_path):  # noqa: F811
    script = [td.READ, td.call("SubmitDraft", BAD, "s1"), td.READ, td.call("ReviseDraft", FIX, "v1")]
    r, model, d = td.run(root, tmp_path, script, config=td.cfg(max_steps=2))
    assert r["status"] == dt.NO_DRAFT and len(model.calls) == 3                    # the revision is never asked for
    tools = [t.__name__ for t in dt.offered({"list_files", "search_files", "read_file"})]
    assert tools[-2:] == ["SubmitDraft", "ReviseDraft"]


def test_a_text_only_reply_in_a_submit_step_ends_the_run(root, tmp_path):  # noqa: F811
    script = [td.READ, td.call("SubmitDraft", BAD, "s1"), td.reply("I am done."), td.call("ReviseDraft", FIX, "v1")]
    r, model, d = td.run(root, tmp_path, script, config=td.cfg(max_steps=2))
    assert r["status"] == dt.NO_DRAFT and len(model.calls) == 3


PROC = ("import sys; sys.path[:0] = [sys.argv[1], sys.argv[1] + '/tests']; import test_drafter_submit_steps as t; "
        "sys.exit(t._proc(*sys.argv[2:]))")


def _proc(root, runs, crash_at, resume):  # noqa: F811
    c = td.cfg(max_steps=2)
    r = dt.run_drafter(run_id="rc", runs_dir=runs, cfg=c, intake_name="shop", issue=td.ISSUE, max_usd=0.4,
                       resume=resume == "1", crash_at=None if crash_at == "-" else crash_at, validate=td.fake_validate,
                       preflight=lambda: (True, "ok"), env_preflight=lambda name: (True, "ok"), root=root,
                       red=td.fake_red)
    return 0 if r["status"] == dt.DRAFTED else 1


def test_a_crash_in_a_submit_step_resumes_there(root, tmp_path):  # noqa: F811
    script = [td._script_reply("ReadFile", {"path": "src/shop.py"}, "r1"), td._script_reply("SubmitDraft", BAD, "s1"),
              td._script_reply("ReviseDraft", FIX, "v1")]
    (tmp_path / "script.json").write_text(json.dumps(script))
    env = {**os.environ, "ARGUS_FAKE_SCRIPT": str(tmp_path / "script.json")}

    def spawn(crash_at, resume):
        return subprocess.run([sys.executable, "-c", PROC, str(ROOT), str(root), str(tmp_path / "runs"), crash_at,
                               resume], cwd=ROOT, capture_output=True, text=True, env=env, timeout=300)
    r1 = spawn("drafter@after_tool:ReviseDraft", "0")
    assert r1.returncode == 42, (r1.stdout[-2000:], r1.stderr[-2000:])
    r2 = spawn("-", "1")
    assert r2.returncode == 0, (r2.stdout[-2000:], r2.stderr[-2000:])
    res = json.loads((tmp_path / "runs" / "rc" / "result.json").read_text())
    assert res["drafting"]["submits"] == 2 and res["drafting"]["steps"] == 2
