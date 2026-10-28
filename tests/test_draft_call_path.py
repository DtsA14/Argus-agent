"""SPEC_DRAFT_CALL_PATH (from the 21379 re-run): a test that keeps an exception and loses its traceback is refused, the
drafter is asked once about the call path outside writable before its draft is accepted, the human sees the same list,
and `argus redraft --note` tells the next drafter a reviewer's note (the job is then human-steered)."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_drafter as td  # noqa: E402
import test_router as tr  # noqa: E402
from test_drafter import root, vlog  # noqa: E402,F401  (the fixtures)
from test_router import env  # noqa: E402,F401  (the fixture)

from codetask import drafter as dt  # noqa: E402
from router import job as rj  # noqa: E402

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="the path jail and flock need posix; the VM runs these")

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "fixtures" / "feedback"
RERUN = json.loads((FIX / "swe_21379_rerun_d1_baseline.json").read_text(encoding="utf-8"))
BATCH3 = json.loads((FIX / "swe_21379_batch3_d1_baseline.json").read_text(encoding="utf-8"))
FRAME = "src/money.py:3: in helper\n    return pay(x)"
QUESTION = "The draft passed its check. Before it is accepted"


def draft_of(scope):
    return {"contract": {"scope": scope}}


def framed(validate=td.fake_validate, frame=FRAME):
    """fake_validate whose failing output also runs through src/money.py, a repository file that is not writable."""
    def run(spec, workspace, sandbox_cfg, log=None):
        r = validate(spec, workspace, sandbox_cfg, log)
        if r["status"] != "pass":
            r["evidence"]["output_tail"] = frame + "\n" + r["evidence"]["output_tail"]
        return r
    return run


def swallowing(spec, workspace, sandbox_cfg, log=None):
    """fake_validate whose failure is an AssertionError reporting a KeyError, with no line of the repository's code."""
    r = td.fake_validate(spec, workspace, sandbox_cfg, log)
    if r["status"] != "pass":
        r["evidence"]["output_tail"] = "____ test_total_never_negative ____\n" + r["evidence"]["output_tail"].replace(
            "E       assert 1 == 0", "E   AssertionError: total() raised KeyError: 'discount'")
    return r


# ---- 2.1 a test that keeps the exception loses its traceback: refused ------------------------------------------------

def test_the_rerun_drafts_test_is_refused_for_losing_the_traceback():
    out = dt.swallowed_problems(draft_of(RERUN["scope"]), RERUN)
    assert len(out) == 1 and "PolynomialError" in out[0] and "test_subs_with_piecewise_hyperbolic_real_symbols" in out[0]
    assert "raise AssertionError" in out[0] and "from the exception" in out[0]


def test_a_test_raising_from_the_exception_or_asserting_a_value_is_not_refused():
    assert dt.swallowed_problems(draft_of(BATCH3["scope"]), BATCH3) == []          # chained: the traceback is there
    plain = {"baseline": {"t": {"status": "fail", "red_check": {"tests/test_a.py::test_a": {"assertion": True}},
                                "output_tail": "tests/test_a.py:5: in test_a\nE       assert 1 == 0\n"}}}
    assert dt.swallowed_problems(draft_of({"writable": ["src/a.py"], "protected": ["tests/**"]}), plain) == []
    plain["baseline"]["t"]["output_tail"] = "tests/test_a.py:5: in test_a\nE   AssertionError: total was 1\n"
    assert dt.swallowed_problems(draft_of({"writable": ["src/a.py"], "protected": ["tests/**"]}), plain) == []


def test_the_drafter_is_told_to_raise_from_the_exception():
    assert "in the except block, raise AssertionError(\"...\") from the exception" in dt.SYSTEM


def test_a_submit_whose_test_swallows_the_traceback_is_rejected(root, tmp_path):  # noqa: F811
    r, model, d = td.run(root, tmp_path, [td.SUBMIT, td.call("ReviseDraft", {}, "v1")], validate=swallowing,
                         config=td.cfg(max_submits=2))
    first = td.tool_texts(model, 1)[0]
    assert first.startswith("Draft rejected") and "reports KeyError" in first and r["status"] != dt.DRAFTED


def section(name, *lines):
    return "\n".join([f"____ {name} ____", *lines])


SWALLOWED_A = section("test_a", "tests/test_a.py:5: in test_a", "E   AssertionError: f() raised KeyError: 'k'")
CHAINED_B = section("test_b", "src/lib.py:9: in f", "E   KeyError: 'k'", "tests/test_a.py:9: in test_b",
                    "E   AssertionError: f() raised KeyError: 'k'")
RED_AB = {"tests/test_a.py::test_a": {"assertion": True}, "tests/test_a.py::test_b": {"assertion": True}}
SCOPE_A = {"writable": ["src/a.py"], "protected": ["tests/**"]}


def base_of(tail):
    return {"baseline": {"t": {"status": "fail", "red_check": RED_AB, "output_tail": tail}}}


def test_each_test_is_judged_by_its_own_section():
    """Review of #208: a test that keeps its traceback does not cover another one in the same validation."""
    out = dt.swallowed_problems(draft_of(SCOPE_A), base_of(CHAINED_B + "\n" + SWALLOWED_A + "\n==== 2 failed ===="))
    assert len(out) == 1 and "tests/test_a.py::test_a" in out[0] and "test_b" not in out[0]


def test_a_section_cut_by_the_start_of_the_tail_is_not_judged():
    cut = "tests/test_a.py:5: in test_a\nE   AssertionError: f() raised KeyError: 'k'\n==== 1 failed ===="
    assert dt.swallowed_problems(draft_of(SCOPE_A), base_of(cut)) == []


def test_pytest_fail_counts_and_test_helpers_are_not_the_repositorys_code():
    fail = section("test_a", "tests/test_a.py:5: in test_a", "E   Failed: f() raised KeyError: 'k'")
    assert len(dt.swallowed_problems(draft_of(SCOPE_A), base_of(fail))) == 1
    helper = section("test_a", "sympy/testing/pytest.py:10: in raises", "tests/test_a.py:5: in test_a",
                     "E   AssertionError: f() raised KeyError: 'k'")
    assert len(dt.swallowed_problems(draft_of(SCOPE_A), base_of(helper))) == 1
    assert dt.call_path_outside(draft_of(SCOPE_A), base_of(helper)) == []


# ---- 2.2 the one scope question ---------------------------------------------------------------------------------------

def test_the_batch3_call_path_outside_writable_starts_at_mod_py():
    out = dt.call_path_outside(draft_of(BATCH3["scope"]), BATCH3)
    assert out[0] == "sympy/core/mod.py:169 (in eval)" and len(out) <= 8
    assert not [x for x in out if "/tests/" in x or x.split(":")[0] in BATCH3["scope"]["writable"]]
    assert "sympy/functions/elementary/hyperbolic.py:251 (in _eval_is_real)" in out
    assert dt.call_path_outside(draft_of(RERUN["scope"]), RERUN) == []           # no repository frame at all


def test_a_draft_that_passes_is_asked_once_then_accepted_as_it_is(root, tmp_path):  # noqa: F811
    r, model, d = td.run(root, tmp_path, [td.SUBMIT, td.call("ReviseDraft", {}, "v1")], validate=framed())
    q = td.tool_texts(model, 1)[0]
    assert q.startswith(QUESTION) and "src/money.py:3 (in helper)" in q
    res = json.loads((d / "result.json").read_text())
    assert r["status"] == dt.DRAFTED and res["drafting"]["submits"] == 2
    assert json.loads((d / "draft.json").read_text())["contract"]["scope"]["writable"] == ["src/shop.py"]
    asked = [e for e in td.events(d) if e["event"] == "draft_submitted" and e.get("scope_question")]
    assert len(asked) == 1 and asked[0]["scope_question"] == ["src/money.py:3 (in helper)"]


def test_a_draft_that_adds_the_file_to_writable_is_accepted(root, tmp_path):  # noqa: F811
    wider = {"scope": {"writable": ["src/**"], "protected": ["tests/**", "conftest.py"]}}
    r, model, d = td.run(root, tmp_path, [td.SUBMIT, td.call("ReviseDraft", wider, "v1")], validate=framed())
    assert r["status"] == dt.DRAFTED
    assert json.loads((d / "draft.json").read_text())["contract"]["scope"]["writable"] == ["src/**"]


def questions(d):
    return [e for e in td.events(d) if e["event"] == "draft_submitted" and e.get("scope_question")]


def test_no_question_without_a_submit_left_or_without_a_call_path(root, tmp_path):  # noqa: F811
    r, model, d = td.run(root, tmp_path, [td.SUBMIT], validate=framed(), config=td.cfg(max_submits=1))
    assert r["status"] == dt.DRAFTED and questions(d) == [] and len(model.calls) == 1
    r, model, d = td.run(root, tmp_path / "b", [td.SUBMIT])                       # nothing outside writable
    assert r["status"] == dt.DRAFTED and questions(d) == []


def test_a_revised_draft_after_the_question_is_not_asked_again(root, tmp_path):  # noqa: F811
    """The answer may change the draft without adding the file (here: unverifiable); it is checked and accepted."""
    other = {"unverifiable": ["the error message reads well", "the floor holds for every discount"]}
    r, model, d = td.run(root, tmp_path, [td.SUBMIT, td.call("ReviseDraft", other, "v1")], validate=framed())
    assert r["status"] == dt.DRAFTED and len(questions(d)) == 1
    assert json.loads((d / "draft.json").read_text())["unverifiable"] == other["unverifiable"]


def test_a_held_draft_is_accepted_when_the_drafter_stops_without_answering(root, tmp_path):  # noqa: F811
    """Review of #208: the draft that passed is kept while the question is open; the run ends DRAFTED with it."""
    r, model, d = td.run(root, tmp_path, [td.SUBMIT] + [td.READ] * 5, validate=framed(), config=td.cfg(max_steps=4))
    assert r["status"] == dt.DRAFTED and td.tool_texts(model, 1)[0].startswith(QUESTION)
    assert [e["after"] for e in td.events(d) if e["event"] == "held_draft_accepted"] == ["max_steps"]


def test_the_same_draft_again_is_accepted_without_a_second_check(root, tmp_path, vlog):  # noqa: F811
    td.run(root, tmp_path / "one", [td.SUBMIT])
    once = len(vlog())                                                    # the validations of one check
    r, model, d = td.run(root, tmp_path, [td.SUBMIT, td.call("ReviseDraft", {}, "v1")], validate=framed())
    assert r["status"] == dt.DRAFTED and once > 0 and len(vlog()) == 2 * once
    assert [e.get("held") for e in td.events(d) if e["event"] == "draft_submitted"] == [None, True]


def test_the_submit_tools_are_version_2_in_the_step_memo_keys(root, tmp_path):  # noqa: F811
    import sqlite3
    r, model, d = td.run(root, tmp_path, [td.READ, td.SUBMIT])
    keys = [json.loads(k) for (k,) in sqlite3.connect(d / "memo.sqlite").execute("select key from memo")]
    versions = sorted({k[-1] for k in keys if k[0] == "tool"})
    assert versions[0] == "2" and len(versions) == 2 and versions[1].startswith("2:")    # ReadFile (line ranges), SubmitDraft


def test_a_question_on_the_last_reading_step_is_answered_in_a_submit_step(root, tmp_path):  # noqa: F811
    """SPEC_DRAFTER_SUBMIT_STEPS: the submit steps after max_steps leave room to answer (no longer refused there)."""
    r, model, d = td.run(root, tmp_path, [td.READ, td.SUBMIT, td.call("ReviseDraft", {}, "v1")], validate=framed(),
                         config=td.cfg(max_steps=2))
    assert r["status"] == dt.DRAFTED and len(questions(d)) == 1 and len(model.calls) == 3


PROC = ("import sys; sys.path[:0] = [sys.argv[1], sys.argv[1] + '/tests']; import test_draft_call_path as t; "
        "sys.exit(t._proc(*sys.argv[2:]))")


def _proc(root, runs, crash_at, resume):  # noqa: F811
    c = td.load_config()
    c["roles"]["drafter"]["model"] = "fake:scripted"
    r = dt.run_drafter(run_id="rc", runs_dir=runs, cfg=c, intake_name="shop", issue=td.ISSUE, max_usd=0.4,
                       resume=resume == "1", crash_at=None if crash_at == "-" else crash_at, validate=framed(),
                       preflight=lambda: (True, "ok"), env_preflight=lambda name: (True, "ok"), root=root,
                       red=td.fake_red)
    return 0 if r["status"] == dt.DRAFTED else 1


def test_a_resumed_drafter_does_not_ask_twice(root, tmp_path):  # noqa: F811
    """The question was asked by the committed first submit; the revision runs again after the crash and, told by
    that record that the question was asked, is accepted (asked again, the scripted model has no reply left)."""
    script = [td._script_reply("SubmitDraft", td.ARGS, "s1"), td._script_reply("ReviseDraft", {}, "v1")]
    (tmp_path / "script.json").write_text(json.dumps(script))
    envs = {**os.environ, "ARGUS_FAKE_SCRIPT": str(tmp_path / "script.json")}

    def spawn(crash_at, resume):
        return subprocess.run([sys.executable, "-c", PROC, str(ROOT), str(root), str(tmp_path / "runs"), crash_at,
                               resume], cwd=ROOT, capture_output=True, text=True, env=envs, timeout=300)
    r1 = spawn("drafter@after_tool:ReviseDraft", "0")
    assert r1.returncode == 42, (r1.stdout[-2000:], r1.stderr[-2000:])
    r2 = spawn("-", "1")
    assert r2.returncode == 0, (r2.stdout[-2000:], r2.stderr[-2000:])
    assert json.loads((tmp_path / "runs" / "rc" / "result.json").read_text())["drafting"]["submits"] == 2


# ---- 2.3 the human sees the same list -----------------------------------------------------------------------------------

def test_the_draft_review_and_the_approve_screen_show_the_call_path(env, monkeypatch):  # noqa: F811
    monkeypatch.setattr(env.deps, "validate", framed(td.fake_validate))
    env.drafter.script[:] = [td.SUBMIT, td.call("ReviseDraft", {}, "v1")]
    env.code()
    st, path = rj._last_draft(env.job())
    review = (path.parent / "DRAFT_REVIEW.md").read_text()
    assert "the failing baseline runs through files that are not writable" in review
    assert "src/money.py:3 (in helper)" in review and "No scope warnings." not in review
    assert "warning: the failing baseline runs through files that are not writable" in rj.status("jtest",
                                                                                                jobs_dir=env.jobs)
    env.approve()
    assert any("src/money.py:3 (in helper)" in c for c in env.confirms if "approve" in c)


# ---- 2.4 redraft --note -----------------------------------------------------------------------------------------------

def test_a_redraft_note_reaches_the_drafter_and_marks_the_job(env):  # noqa: F811
    env.code()
    env.drafter.script[:] = [td.SUBMIT]
    job, _ = rj.redraft("jtest", cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs, note="look at src/shop.py\x1b[31m")
    st = job.data["stages"]["d2"]
    assert st["note"] == "look at src/shop.py" and job.data["human_steered"] is True
    prompt = "\n".join(m.content if isinstance(m.content, str) else json.dumps(m.content)
                       for m in env.drafter.calls[-1]["messages"])
    assert dt.NOTE_LABEL in prompt and "look at src/shop.py" in prompt and "\x1b" not in prompt
    inputs = json.loads((job.runs / st["run_id"] / "inputs.json").read_text())
    assert inputs["note"] == st["note"]
    text = rj.status("jtest", jobs_dir=env.jobs)
    assert "human-steered" in text and "note: look at src/shop.py" in text
    job.data["stages"]["d2"]["note"] = "y" * 1000
    job.save()
    line = [x for x in rj.status("jtest", jobs_dir=env.jobs).splitlines() if "note:" in x][0]
    assert line.endswith("; note: " + "y" * 80 + "...")                # the full note stays in job.json
    assert "Note from the reviewer (human-steered)" in (job.runs / st["run_id"] / "DRAFT_REVIEW.md").read_text()


def test_a_note_too_long_or_empty_starts_nothing(env):  # noqa: F811
    env.code()
    before = json.dumps(env.job().data, sort_keys=True)
    for note in ["x" * 1001, "  \x07 "]:
        with pytest.raises(rj.Refused):
            rj.redraft("jtest", cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs, note=note)
    assert json.dumps(env.job().data, sort_keys=True) == before


def test_without_a_note_the_drafter_prompt_is_as_it_was():
    policy = {"environment": "e", "validation_timeout_s": 1, "profile_info": {}, "agent_tools": [], "max_submits": 5}
    base = {"intake": "i", "issue": "the issue", "max_usd": 0.5}
    assert dt.NOTE_LABEL not in dt.task_prompt(base, 3, policy)
    with_note = dt.task_prompt({**base, "note": "n"}, 3, policy)
    assert with_note.replace(f"{dt.NOTE_LABEL}\nn\n\n", "") == dt.task_prompt(base, 3, policy)


def test_the_cli_passes_the_note_to_redraft(env, monkeypatch):  # noqa: F811
    import importlib.util
    spec = importlib.util.spec_from_file_location("argus_cli_note", ROOT / "scripts" / "argus.py")
    cli = importlib.util.module_from_spec(spec)
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    spec.loader.exec_module(cli)
    seen = {}

    def fake(job_id, **kw):
        seen.update(kw, job=job_id)
        raise rj.Refused("stop here")
    monkeypatch.setattr(rj, "redraft", fake)
    assert cli.main(["--jobs-dir", str(env.jobs), "redraft", "j1", "--note", "hello"], deps=env.deps) == 2
    assert seen["job"] == "j1" and seen["note"] == "hello"
