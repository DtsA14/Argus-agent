"""M6 W2b (docs/reviews/SPEC_W2B_DRAFTER.md): a model drafts a task from an issue and an intake, read-only, and every
SubmitDraft is checked at once (W2a's static checks and baseline red, without a reference patch). Scripted models and
an injected validation that reads the materialized tree like pytest would (no Docker); crash-resume across processes
through scripts/draft_task.py's run_drafter in a subprocess. The real sandbox check of a no-reference draft is in
tests/test_draft.py."""
import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from acceptance import changed as ch
from acceptance import draft as dr
from acceptance import intake
from acceptance.workspace import digest, snapshot
from codetask import drafter as dt
from harness.events import EventLog
from models.fake import StrictScriptedChatModel, reply
from runner import load_config

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="the path jail needs openat; the VM runs these")

ROOT = Path(__file__).resolve().parent.parent
BUGGY = "def total(prices, discount):\n    return sum(prices) - discount\n"
FIXED = "def total(prices, discount):\n    return max(sum(prices) - discount, 0)\n"
OLD_TEST = "from src.shop import total\n\n\ndef test_total_plain():\n    assert total([2, 3], 1) == 4\n"
NEW_TEST = "from src.shop import total\n\n\ndef test_total_never_negative():\n    assert total([1], 5) == 0\n"
GREEN_TEST = NEW_TEST.replace("== 0", "== -4")
BROKEN_TEST = "import nosuchmodule\n\n\ndef test_total_never_negative():\n    assert False\n"
NEW_NODE = "tests/test_new.py::test_total_never_negative"
OLD_NODE = "tests/test_old.py::test_total_plain"
ISSUE = "total() can go negative when the discount is larger than the sum; it must never be below 0."
CHANGED_OLD = OLD_TEST + "\n\ndef test_total_floor():\n    assert total([1], 5) == 0\n"     # W2a-ext
FLOOR_NODE = "tests/test_old.py::test_total_floor"

ARGS = {"plan": {"files": ["src/shop.py"], "steps": ["floor the total at 0"], "risks": ["a discount of 0"]},
        "scope": {"writable": ["src/shop.py"], "protected": ["tests/**", "conftest.py"]},
        "validation": [{"id": "target", "paths": ["tests/test_new.py"], "must_pass": [NEW_NODE], "min_tests": 1},
                       {"id": "regression", "paths": ["tests/test_old.py"], "must_pass": [OLD_NODE], "min_tests": 1}],
        "new_tests": [{"path": "tests/test_new.py", "content": NEW_TEST}],
        "unverifiable": ["the error message reads well"], "budget_profile": "large_usd"}


def args_with(test=None, **over):
    a = copy.deepcopy(ARGS)
    if test is not None:
        a["new_tests"][0]["content"] = test
    a.update(over)
    return a


def call(name, args, id):
    return reply(tool_calls=[{"name": name, "args": args, "id": id}], input_tokens=500, output_tokens=60)


READ = call("ReadFile", {"path": "src/shop.py"}, "r1")
SUBMIT = call("SubmitDraft", ARGS, "s1")


def git(repo, *args):
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@x", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env)


def make_root(tmp_path):
    """A project root with one intake, `shop`: a bug, one existing test."""
    repo = tmp_path / "shop_repo"
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "conftest.py").write_text("")
    (repo / "src" / "shop.py").write_text(BUGGY)
    (repo / "tests" / "test_old.py").write_text(OLD_TEST)
    git(tmp_path, "init", "-q", str(repo))
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "base")
    proj = tmp_path / "proj"
    proj.mkdir()
    intake.intake(repo, "HEAD", "shop", root=proj)
    return proj


@pytest.fixture
def root(tmp_path):
    return make_root(tmp_path)


def _functions(text):
    """{test name: its body} of a test file, as pytest would collect it."""
    out = {}
    for part in ("\n" + text).split("\ndef ")[1:]:
        name = part.split("(", 1)[0]
        if name.startswith("test_"):
            out[name] = part
    return out


def fake_validate(spec, workspace, sandbox_cfg, log=None):
    """Stands in for `python -m pytest <paths>` in the sandbox: a test fails by assertion when it asserts the floor at 0
    and the bug is there; a file that imports a missing module is a collection error. Every call is counted in the
    file named by ARGUS_TEST_VALIDATE_LOG (also across processes)."""
    if os.environ.get("ARGUS_TEST_VALIDATE_LOG"):
        with open(os.environ["ARGUS_TEST_VALIDATE_LOG"], "a") as f:
            f.write(spec["id"] + "\n")
    ws, fixed = Path(workspace), (Path(workspace) / "src" / "shop.py").read_text() == FIXED
    statuses, tail, errors = {}, [], 0
    for path in spec["args"][2:]:
        f = ws / path
        text = f.read_text() if f.exists() else ""
        if "nosuchmodule" in text:
            errors += 1
            tail += [f"{path}:1: in <module>", "E   ModuleNotFoundError: No module named 'nosuchmodule'"]
            continue
        for name, body in _functions(text).items():
            bad = "== 0" in body and not fixed
            statuses[f"{path}::{name}"] = "FAIL" if bad else "ok"
            if bad:
                tail += [f"{path}:5: in {name}", "E       assert 1 == 0", "E        +  where 1 = total([1], 5)"]
    failures = sum(1 for s in statuses.values() if s == "FAIL")
    tail.append(f"==== {failures} failed, {len(statuses) - failures} passed, {errors} errors in 0.12s ====")
    must = {n: statuses.get(n) for n in spec.get("must_pass", [])}
    ok = not failures and not errors and all(v == "ok" for v in must.values())
    return {"id": f"validation:{spec['id']}", "layer": "C", "status": "pass" if ok else "fail",
            "reason": "" if ok else "exit code 1",
            "evidence": {"must_pass": must, "tests_run": len(statuses), "failures": failures, "errors": errors,
                         "skipped": 0, "consistent": True, "output_tail": "\n".join(tail),
                         "failed_nodes": sorted(n for n, s in statuses.items() if s == "FAIL")}}


def fake_collect(path, workspace, sandbox_cfg, **kw):
    """Stands in for `pytest --collect-only` in the sandbox (W2a-ext K1)."""
    f = Path(workspace) / path
    return ({f"{path}::{n}" for n in _functions(f.read_text())} if f.exists() else set()), None


def fake_red(nodes, workspace, sandbox_cfg, **kw):
    """Stands in for the W2a red check in the sandbox: every node fake_validate fails, fails by an assert of its file."""
    return {n: {"outcome": "failed", "type": "builtins.AssertionError", "assertion": True, "path": n.split("::", 1)[0]}
            for n in nodes}, None


def cfg(**drafter):
    c = load_config()
    c["roles"]["drafter"]["model"] = "fake:scripted"
    c["drafter"].update(drafter)
    return c


def run(root, tmp_path, script, *, issue=ISSUE, max_usd=0.4, config=None, validate=fake_validate, run_id="d",
        intake_name="shop", preflight=lambda: (True, "ok"), red=None):
    red = red or fake_red
    model = StrictScriptedChatModel(script=list(script))
    r = dt.run_drafter(run_id=run_id, runs_dir=tmp_path / "runs", cfg=config or cfg(), intake_name=intake_name,
                       issue=issue, max_usd=max_usd, models={"drafter": model}, validate=validate,
                       preflight=preflight, env_preflight=lambda name: (True, "ok"), root=root, collect=fake_collect,
                       red=red)
    return r, model, tmp_path / "runs" / run_id


def events(run_dir):
    return [json.loads(line) for line in (run_dir / "events.jsonl").read_text().splitlines() if line.strip()]


def tool_texts(model, n):
    """The tool results the model saw in its n-th call (0-based)."""
    return [m.content for m in model.calls[n]["messages"] if type(m).__name__ == "ToolMessage"]


@pytest.fixture
def vlog(tmp_path, monkeypatch):
    p = tmp_path / "validate.log"
    monkeypatch.setenv("ARGUS_TEST_VALIDATE_LOG", str(p))
    return lambda: p.read_text().splitlines() if p.exists() else []


# ---- the happy path -----------------------------------------------------------------------------------------------

def test_a_draft_that_passes_its_check_ends_the_run_and_is_written_for_the_human(root, tmp_path, vlog):
    r, model, d = run(root, tmp_path, [READ, SUBMIT])
    assert r["status"] == dt.DRAFTED and r["drafting"] == {"end": "submitted", "steps": 1, "submits": 1}
    assert len(model.calls) == 2 and r["llm_calls"] == 2 and r["usd_billed"] > 0 and r["usd_complete"]
    assert r["source_unchanged"] is True and vlog() == ["target", "regression"]
    draft = json.loads((d / "draft.json").read_text())
    # Set by the harness, not the model: the intake, the version, and every validation's command and environment
    assert draft["base"] == "shop" and draft["draft_version"] == dr.VERSION
    assert draft["contract"]["validation"][0] == {
        "id": "target", "executable": "python", "args": ["-m", "pytest", "tests/test_new.py"], "timeout_s": 300,
        "min_tests": 1, "max_skipped": 0, "must_pass": [NEW_NODE], "environment": "argus"}
    # The same draft passes W2a's check outside the loop, with the same baseline
    again = dr.check(draft, task="fix_shop", issue=ISSUE, max_usd=0.5, max_iterations=3, reference_patch=None,
                     sandbox_cfg={}, root=root, validate=fake_validate, red=fake_red, profiles=None)
    assert again["ok"] and again["baseline"]["target"]["must_pass"] == {NEW_NODE: "FAIL"}
    report = json.loads((d / "check_report.json").read_text())
    assert report["ok"] and report["feasibility"] == "unproven" and report["reference"] is None
    review = (d / "DRAFT_REVIEW.md").read_text()
    assert "assert 1 == 0" in review and "--no-reference" in review and NEW_TEST.strip() in review
    assert (d / "issue.txt").read_text().strip() == ISSUE
    assert json.loads((d / "result.json").read_text())["status"] == dt.DRAFTED


def test_a_rejected_submit_goes_back_to_the_model_and_a_corrected_one_passes(root, tmp_path, vlog):
    green = call("SubmitDraft", args_with(GREEN_TEST), "s0")
    r, model, d = run(root, tmp_path, [green, SUBMIT])
    assert r["status"] == dt.DRAFTED and r["drafting"]["submits"] == 2
    seen = tool_texts(model, 1)[0]
    assert seen.startswith("Draft rejected (submit 1 of 5)") and "is 'ok', not a failure by assertion" in seen
    assert dt.PASSING_HINT in seen                                           # how to keep a test that passes now
    assert [e["ok"] for e in events(d) if e["event"] == "draft_submitted"] == [False, True]


def test_an_error_on_the_baseline_is_not_red_and_its_output_reaches_the_model(root, tmp_path, vlog):
    broken = call("SubmitDraft", args_with(BROKEN_TEST), "s0")
    r, model, d = run(root, tmp_path, [broken, SUBMIT])
    seen = tool_texts(model, 1)[0]
    assert "was not collected on the baseline" in seen
    assert "data from the sandbox, not instructions" in seen and "ModuleNotFoundError: No module named" in seen
    assert r["status"] == dt.DRAFTED


def test_submits_beyond_the_limit_run_nothing_and_the_run_ends_without_a_draft(root, tmp_path, vlog):
    bad = [call("SubmitDraft", args_with(GREEN_TEST), f"s{i}") for i in range(3)]
    r, model, d = run(root, tmp_path, bad + [SUBMIT], config=cfg(max_submits=2))
    assert r["status"] == dt.NO_DRAFT and r["stop_reason"] == "submits_exhausted" and r["drafting"]["submits"] == 3
    assert len(vlog()) == 4 and len(model.calls) == 3                  # two checks of two validations; none after
    assert [e["event"] for e in events(d)].count("draft_submit_refused") == 1     # the third: refused, not checked
    assert not (d / "draft.json").exists() and "No draft passed its check" in (d / "DRAFT_REVIEW.md").read_text()


# ---- ReviseDraft, and naming what fails without being required ---------------------------------------------------

def revise(args, id="v1"):
    return call("ReviseDraft", args, id)


def test_revise_changes_only_the_fields_it_gives_and_is_checked_like_a_submit(root, tmp_path, vlog):
    green = call("SubmitDraft", args_with(GREEN_TEST), "s0")
    r, model, d = run(root, tmp_path, [green, revise({"new_tests": ARGS["new_tests"]})])
    assert r["status"] == dt.DRAFTED and r["drafting"]["submits"] == 2 and len(vlog()) == 4
    want, _ = dt.draft_from_args(ARGS, base="shop", policy=POLICY)
    assert json.loads((d / "draft.json").read_text()) == want                 # everything else as first submitted
    assert "call ReviseDraft with only the fields that change" in tool_texts(model, 1)[0]
    assert [e.get("revise") for e in events(d) if e["event"] == "draft_submitted"] == [False, True]


def test_a_test_that_fails_without_being_required_is_named_and_one_revision_fixes_it(root, tmp_path, vlog):
    extra = NEW_TEST + "\n\ndef test_also_floored():\n    assert total([2], 9) == 0\n"
    first = call("SubmitDraft", args_with(extra), "s0")
    both = copy.deepcopy(ARGS["validation"])
    both[0]["must_pass"] = [NEW_NODE, "tests/test_new.py::test_also_floored"]
    r, model, d = run(root, tmp_path, [first, revise({"validation": both})])
    seen = tool_texts(model, 1)[0]
    assert "failing or erroring but not required: tests/test_new.py::test_also_floored" in seen
    assert r["status"] == dt.DRAFTED and r["drafting"]["submits"] == 2
    draft = json.loads((d / "draft.json").read_text())
    assert draft["new_tests"][0]["content"] == extra and len(draft["contract"]["validation"][0]["must_pass"]) == 2


def test_revise_without_a_submitted_draft_runs_nothing_and_counts(root, tmp_path, vlog):
    r, model, d = run(root, tmp_path, [revise({"unverifiable": []}), SUBMIT])
    assert tool_texts(model, 1)[0].startswith("Rejected: there is no submitted draft to revise")
    assert r["status"] == dt.DRAFTED and r["drafting"]["submits"] == 2 and vlog() == ["target", "regression"]


def test_revise_cannot_set_what_a_drafter_may_not_set(root, tmp_path, vlog):
    green = call("SubmitDraft", args_with(GREEN_TEST), "s0")
    r, model, d = run(root, tmp_path, [green, revise({"base": "other", "new_tests": ARGS["new_tests"]}), SUBMIT])
    assert "unknown argument 'base'" in tool_texts(model, 2)[1] and len(vlog()) == 4     # the bad revision ran nothing
    assert json.loads((d / "draft.json").read_text())["base"] == "shop"


def test_revisions_count_toward_the_submit_limit(root, tmp_path, vlog):
    green = call("SubmitDraft", args_with(GREEN_TEST), "s0")
    still = revise({"plan": ARGS["plan"]})
    r, model, d = run(root, tmp_path, [green, still, revise({"plan": ARGS["plan"]}, "v2"), SUBMIT],
                      config=cfg(max_submits=2))
    assert r["status"] == dt.NO_DRAFT and r["stop_reason"] == "submits_exhausted" and len(vlog()) == 4


def test_revisedraft_with_another_call_runs_nothing(root, tmp_path, vlog):
    both = reply(tool_calls=[{"name": "ReadFile", "args": {"path": "src/shop.py"}, "id": "r"},
                             {"name": "ReviseDraft", "args": {"plan": ARGS["plan"]}, "id": "v"}],
                 input_tokens=500, output_tokens=60)
    r, model, _ = run(root, tmp_path, [both, SUBMIT])
    assert all("must be the only tool call" in t for t in tool_texts(model, 1)) and r["drafting"]["submits"] == 1


# ---- read-only, and what the model may not set ---------------------------------------------------------------------

def test_the_drafter_cannot_write_validate_or_finish_and_the_intake_is_untouched(root, tmp_path, vlog):
    before = intake.check(intake.record_for("fixtures/repos/shop", root), root / "fixtures" / "repos" / "shop")
    tries = reply(tool_calls=[{"name": "WriteFile", "args": {"path": "src/shop.py", "content": FIXED}, "id": "w"},
                              {"name": "EditFile", "args": {"path": "src/shop.py", "old_text": "sum", "new_text": "x"},
                               "id": "e"},
                              {"name": "RunValidation", "args": {"id": "target"}, "id": "v"},
                              {"name": "Finish", "args": {"claims": [], "summary": "x"}, "id": "f"}],
                  input_tokens=500, output_tokens=60)
    r, model, d = run(root, tmp_path, [tries, SUBMIT])
    seen = tool_texts(model, 1)
    assert seen == [f"Denied: {n} is not allowed for this role." for n in ("WriteFile", "EditFile", "RunValidation")] \
        + ["Unknown tool 'Finish'."]
    denied = [e for e in events(d) if e["event"] == "tool_denied"]
    assert [e["tool"] for e in denied] == ["write_file", "edit_file", "run_validation"]
    assert {e["role"] for e in denied} == {"drafter"}
    assert vlog() == ["target", "regression"]                           # only the SubmitDraft check ran
    assert (d / "source" / "src" / "shop.py").read_text() == BUGGY and not (d / "source" / "SUMMARY.json").exists()
    assert r["source_unchanged"] is True and r["status"] == dt.DRAFTED
    assert before == [] and intake.check(intake.record_for("fixtures/repos/shop", root),
                                         root / "fixtures" / "repos" / "shop") == []


def test_a_changed_source_copy_blocks_the_run(root, tmp_path, monkeypatch):
    real = dt.make_submit

    def tampering(**kw):
        submit = real(**kw)

        def wrapped(args, n, **kw):
            (tmp_path / "runs" / "d" / "source" / "src" / "shop.py").write_text(FIXED)
            return submit(args, n, **kw)
        return wrapped
    monkeypatch.setattr(dt, "make_submit", tampering)
    r, _, d = run(root, tmp_path, [SUBMIT])
    assert r["status"] == dt.BLOCKED and r["blocked_reason"] == "source_changed" and r["source_unchanged"] is False
    assert not (d / "draft.json").exists()


POLICY = {"environment": "argus", "validation_timeout_s": 300, "profiles": ["default", "large_usd"], "max_submits": 3}


@pytest.mark.parametrize("change, why", [
    (lambda a: a.update(base="other"), "unknown argument 'base'"),
    (lambda a: a.update(draft_version=2), "unknown argument 'draft_version'"),
    (lambda a: a.update(limits={"max_usd": 9}), "unknown argument 'limits'"),
    (lambda a: a.update(inputs={"issue": "x"}), "unknown argument 'inputs'"),
    (lambda a: a["validation"][0].update(executable="bash"), "no other command"),
    (lambda a: a["validation"][0].update(environment="default"), "no other command"),
    (lambda a: a["validation"][0].update(paths=["-p", "evil"]), "no options"),
    (lambda a: a["validation"][0].update(paths=["--rootdir=/"]), "no options"),
    (lambda a: a["validation"][0].update(paths=["../outside/test_x.py"]), "no options"),
    (lambda a: a["validation"][0].update(paths=["/etc/test_x.py"]), "no options"),
    (lambda a: a["validation"][0].update(paths=[]), "no options"),
    (lambda a: a.update(validation=[]), "validation must be a non-empty list"),
    (lambda a: a.update(budget_profile="huge"), "budget_profile is required and must be one of"),
    (lambda a: a.pop("budget_profile"), "budget_profile is required and must be one of"),
    (lambda a: a.update(budget_profile=None), "budget_profile is required and must be one of"),
    (lambda a: a.update(tools=["write_file"]), "tools must be a list of distinct names from"),
    (lambda a: a.update(tools=["edit_file", "edit_file"]), "tools must be a list of distinct names from"),
    (lambda a: a.update(tools="edit_file"), "tools must be a list of distinct names from"),
    (lambda a: a.update(new_tests=[]), "at least one new test"),
    (lambda a: a["plan"].pop("risks"), "plan must have"),
])
def test_the_model_sets_only_what_a_drafter_may_set(change, why):
    a = copy.deepcopy(ARGS)
    change(a)
    draft, problems = dt.draft_from_args(a, base="shop", policy=POLICY)
    assert any(why in p for p in problems), problems


def test_the_harness_sets_the_base_the_version_and_each_validations_command():
    draft, problems = dt.draft_from_args(ARGS, base="shop", policy=POLICY)
    assert problems == [] and draft["base"] == "shop" and draft["draft_version"] == dr.VERSION
    assert draft["contract"]["budget_profile"] == "large_usd"
    assert [v["args"] for v in draft["contract"]["validation"]] == [["-m", "pytest", "tests/test_new.py"],
                                                                     ["-m", "pytest", "tests/test_old.py"]]
    assert {v["environment"] for v in draft["contract"]["validation"]} == {"argus"}
    assert dt.draft_from_args(dict(ARGS, validation=[dict(ARGS["validation"][0], paths=[NEW_NODE])]), base="shop",
                              policy=POLICY)[1] == []                       # a node id is a path too


def test_a_bad_submit_is_answered_without_running_anything(root, tmp_path, vlog):
    r, model, d = run(root, tmp_path, [call("SubmitDraft", args_with(base="other"), "s0"), SUBMIT])
    assert "unknown argument 'base'" in tool_texts(model, 1)[0] and vlog() == ["target", "regression"]
    assert r["status"] == dt.DRAFTED and r["drafting"]["submits"] == 2


# ---- inputs ---------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("over, why", [
    ({"issue": ""}, "at most 2000 characters"),
    ({"issue": "x" * 2001}, "at most 2000 characters"),
    ({"intake_name": "nosuch"}, "no intake named 'nosuch'"),
    ({"intake_name": "Bad Name"}, "is not an intake name"),
])
def test_bad_inputs_block_before_any_model_call(root, tmp_path, over, why):
    r, model, d = run(root, tmp_path, [SUBMIT], **over)
    assert r["status"] == dt.BLOCKED and r["blocked_reason"] == "invalid_input" and why in r["stop_reason"]
    assert model.calls == [] and r["llm_calls"] == 0


def test_a_changed_intake_blocks_the_run(root, tmp_path):
    (root / "fixtures" / "repos" / "shop" / "src" / "shop.py").write_text(FIXED)
    r, model, _ = run(root, tmp_path, [SUBMIT])
    assert r["blocked_reason"] == "invalid_input" and "changed" in r["stop_reason"] and model.calls == []


def test_a_task_cannot_be_drafted_on_another_task(root, tmp_path):
    rec_path = root / "fixtures" / "intake" / "shop.json"
    rec = json.loads(rec_path.read_text())
    rec_path.write_text(json.dumps({**rec, "kind": "task"}))
    r, model, _ = run(root, tmp_path, [SUBMIT])
    assert r["blocked_reason"] == "invalid_input" and "another task" in r["stop_reason"] and model.calls == []


def test_no_sandbox_blocks_before_any_model_call(root, tmp_path):
    r, model, _ = run(root, tmp_path, [SUBMIT], preflight=lambda: (False, "no docker"))
    assert r["status"] == dt.BLOCKED and r["blocked_reason"] == "sandbox_unavailable" and model.calls == []


# ---- money ----------------------------------------------------------------------------------------------------------

def test_a_call_that_does_not_fit_the_runs_cap_is_refused_before_sending(root, tmp_path):
    r, model, d = run(root, tmp_path, [READ, SUBMIT], max_usd=0.0001)
    assert model.calls == [] and r["status"] == dt.NO_DRAFT and r["stop_reason"] == "reservation_exhausted"
    evs = events(d)
    assert [e["status"] for e in evs if e["event"] == "llm_call"] == ["refused"] and r["usd_billed"] == 0
    assert r["max_usd"] == 0.0001


def test_the_runs_cap_is_the_lower_of_the_config_and_the_run(root, tmp_path):
    c = cfg()
    c["budget"]["max_usd"] = 0.2
    r, _, d = run(root, tmp_path, [READ, SUBMIT], max_usd=0.9, config=c)
    assert r["max_usd"] == 0.2
    assert dt.drafter_settings({**c, "budget": {**c["budget"], "max_usd": 0.2}})["attempt_usd"] == 0.2
    assert dt.drafter_settings({**c, "budget": {**c["budget"], "max_tokens": 1000}})["attempt_tokens"] == 1000
    started = [e for e in events(d) if e["event"] == "llm_call_started"]
    assert started and all(e["node"] == "drafter" and e["task"] == "draft:shop" for e in started)


def test_every_call_reaches_the_ledger_with_a_start_and_an_end(root, tmp_path):
    _, _, d = run(root, tmp_path, [READ, SUBMIT])
    evs = events(d)
    started = [e["call_id"] for e in evs if e["event"] == "llm_call_started"]
    ended = [e["call_id"] for e in evs if e["event"] == "llm_call"]
    assert len(started) == 2 and started == ended


# ---- loop shape ------------------------------------------------------------------------------------------------------

def test_a_cut_off_reply_ends_the_run_without_a_draft(root, tmp_path):
    r, _, _ = run(root, tmp_path, [reply("partial", stop_reason="max_tokens")])
    assert r["status"] == dt.NO_DRAFT and r["stop_reason"] == "output_truncated"


def test_a_reply_without_tools_is_nudged_to_submit(root, tmp_path):
    r, model, _ = run(root, tmp_path, [reply("let me think"), SUBMIT])
    last = model.calls[1]["messages"][-1]
    assert type(last).__name__ == "HumanMessage" and "SubmitDraft" in last.content and "Finish" not in last.content
    assert r["status"] == dt.DRAFTED


def test_submitdraft_with_another_call_in_the_same_reply_runs_nothing(root, tmp_path, vlog):
    both = reply(tool_calls=[{"name": "ReadFile", "args": {"path": "src/shop.py"}, "id": "r"},
                             {"name": "SubmitDraft", "args": ARGS, "id": "s"}], input_tokens=500, output_tokens=60)
    r, model, d = run(root, tmp_path, [both, SUBMIT])
    assert all("must be the only tool call" in t for t in tool_texts(model, 1)) and len(tool_texts(model, 1)) == 2
    assert vlog() == ["target", "regression"] and r["drafting"]["submits"] == 1


def test_max_steps_ends_the_run(root, tmp_path):
    reads = [call("ReadFile", {"path": "src/shop.py"}, f"r{i}") for i in range(3)]
    r, model, _ = run(root, tmp_path, reads, config=cfg(max_steps=3))
    assert r["status"] == dt.NO_DRAFT and r["stop_reason"] == "max_steps" and len(model.calls) == 3


# ---- the review page ---------------------------------------------------------------------------------------------

def test_scope_warnings_name_patterns_test_paths_and_files_outside_the_plan():
    d = {"plan": {"files": ["src/a.py"]},
         "contract": {"scope": {"writable": ["src/a.py", "src/*.py", "tests/test_a.py", "src/b.py"]}}}
    w = dt.warnings(d)
    assert any("`src/*.py` is a pattern" in x for x in w) and any("`tests/test_a.py` looks like a test" in x for x in w)
    assert any("`src/b.py` is not among the plan's files" in x for x in w)
    assert not any("`src/a.py`" in x for x in w)


def test_the_review_page_is_the_golden_one():
    draft, _ = dt.draft_from_args(dict(ARGS, scope={"writable": ["src/*.py"], "protected": ["tests/**"]}),
                                  base="shop", policy=POLICY)
    tail = fake_validate(draft["contract"]["validation"][0], _materialized(draft), {})["evidence"]["output_tail"]
    state = {"status": dt.DRAFTED, "stop_reason": "a draft passed its check", "draft": draft,
             "report": {"baseline": {"target": {"status": "fail", "must_pass": {NEW_NODE: "FAIL"}, "failures": 1,
                                                "errors": 0, "output_tail": tail},
                                     "regression": {"status": "pass", "must_pass": {OLD_NODE: "ok"}, "failures": 0,
                                                    "errors": 0, "output_tail": ""}}},
             "drafting": {"end": "submitted", "steps": 3, "submits": 1}}
    text = dt.review_text("d1", {"intake": "shop", "issue": ISSUE}, state,
                          {"usd": 0.0123, "usd_complete": True, "calls": 4})
    golden = Path(__file__).parent / "golden" / "draft_review.md"
    assert text == golden.read_text(encoding="utf-8")


def changed_args(content, **entry):
    """ARGS that also change tests/test_old.py, with its new required test in the regression validation."""
    a = copy.deepcopy(ARGS)
    a["validation"][1]["must_pass"] = [FLOOR_NODE]
    a["changed_tests"] = [{"path": "tests/test_old.py", "content": content, **entry}]
    return a


def test_changed_tests_go_through_submit_and_revise_and_a_lost_test_is_named(root, tmp_path, vlog):
    renamed = CHANGED_OLD.replace("test_total_plain", "test_total_renamed")
    lost = call("SubmitDraft", changed_args(renamed), "s0")
    fixed = call("ReviseDraft", {"changed_tests": [{"path": "tests/test_old.py", "content": CHANGED_OLD}]}, "s1")
    r, model, d = run(root, tmp_path, [lost, fixed])
    assert r["status"] == dt.DRAFTED and r["drafting"]["submits"] == 2
    seen = tool_texts(model, 1)[0]
    assert "loses 1 test(s) not listed in removed: tests/test_old.py::test_total_plain" in seen
    assert "restore them, or list them in removed with a reason" in seen
    draft = json.loads((d / "draft.json").read_text())
    assert draft["changed_tests"] == [{"path": "tests/test_old.py", "content": CHANGED_OLD}]
    assert draft["contract"]["validation"][1]["must_pass"] == [FLOOR_NODE]       # kept from the SubmitDraft
    report = json.loads((d / "check_report.json").read_text())
    assert report["baseline"]["regression"]["must_pass"] == {FLOOR_NODE: "FAIL"}
    assert report["contract"]["validation"][1]["no_skip"] == {"paths": ["tests/test_old.py"], "allowed": []}
    review = (d / "DRAFT_REVIEW.md").read_text()
    assert "## Existing tests changed" in review and "+def test_total_floor():" in review
    assert "No warnings (K3)." in review


def test_a_test_red_by_a_key_error_is_refused_and_the_drafter_is_told_how_to_assert_instead(root, tmp_path, vlog):
    # docs/reviews/SPEC_W2A_RED_BY_ASSERTION.md: the first check sees a KeyError, the second an assertion
    seen_by_red = []

    def red(nodes, workspace, sandbox_cfg, **kw):
        seen_by_red.append(list(nodes))
        first = len(seen_by_red) == 1
        return {n: {"outcome": "failed", "type": "builtins.KeyError" if first else "builtins.AssertionError",
                    "assertion": not first, "path": n.split("::", 1)[0]} for n in nodes}, None
    r, model, d = run(root, tmp_path, [SUBMIT, call("SubmitDraft", ARGS, "s2")], red=red)
    seen = tool_texts(model, 1)[0]
    assert f"required test {NEW_NODE} fails with builtins.KeyError, not by an assertion" in seen
    assert 'assert "key" in report' in seen
    assert r["status"] == dt.DRAFTED and r["drafting"]["submits"] == 2 and seen_by_red == [[NEW_NODE], [NEW_NODE]]


def test_a_draft_without_changed_tests_has_none():
    draft, problems = dt.draft_from_args(dict(ARGS, changed_tests=[]), base="shop", policy=POLICY)
    assert problems == [] and "changed_tests" not in draft


WEAKER = "import pytest\n" + OLD_TEST.replace("assert total([2, 3], 1) == 4", "pytest.skip('later')")
WEAKER_ENTRY = {"path": "tests/test_old.py", "content": WEAKER,
                "removed": [{"node": "test_total_gone", "reason": "merged into test_total_plain"}],
                "modified": [{"node": "test_total_plain", "reason": "skipped until the fix"}]}


def test_the_review_page_shows_a_changed_tests_diff_what_it_removes_and_modifies_and_the_k3_warnings(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_old.py").write_text(OLD_TEST)
    draft, _ = dt.draft_from_args(dict(ARGS, changed_tests=[WEAKER_ENTRY]), base="shop", policy=POLICY)
    warn = ch.warnings("tests/test_old.py", OLD_TEST, WEAKER, WEAKER_ENTRY["removed"])
    state = {"status": dt.DRAFTED, "draft": draft, "report": {"warnings": warn}, "drafting": {}}
    text = dt.review_text("d1", {"intake": "shop", "issue": ISSUE}, state,
                          {"usd": 0.01, "usd_complete": True, "calls": 1}, tmp_path)
    assert "## Existing tests changed" in text and "### `tests/test_old.py`" in text
    assert "-    assert total([2, 3], 1) == 4" in text and "+    pytest.skip('later')" in text
    assert "- removed `test_total_gone`: merged into test_total_plain" in text
    assert "- modified `test_total_plain`: skipped until the fix" in text
    assert "tests/test_old.py::test_total_plain has fewer asserts (1 -> 0)" in text
    assert "tests/test_old.py has more skip, xfail or `assert True` (0 -> 1)" in text
    assert "tests/test_old.py changes module-level code" in text and len(warn) == 4


def _materialized(draft, _cache={}):
    """A tree with the bug and the draft's new test, for the golden page's test output."""
    import tempfile
    if "d" not in _cache:
        d = Path(tempfile.mkdtemp())
        (d / "src").mkdir()
        (d / "tests").mkdir()
        (d / "src" / "shop.py").write_text(BUGGY)
        (d / "tests" / "test_new.py").write_text(draft["new_tests"][0]["content"])
        _cache["d"] = d
    return _cache["d"]


# ---- crash-resume across processes -------------------------------------------------------------------------------

PROC = ("import sys, json; sys.path[:0] = [sys.argv[1], sys.argv[1] + '/tests']; import test_drafter as t; "
        "sys.exit(t._proc(*sys.argv[2:]))")


def _proc(root, runs, crash_at, resume):
    """One process of a drafter run with the scripted model of ARGUS_FAKE_SCRIPT (its position survives a crash)."""
    c = load_config()
    c["roles"]["drafter"]["model"] = "fake:scripted"
    r = dt.run_drafter(run_id="rc", runs_dir=runs, cfg=c, intake_name="shop", issue=ISSUE, max_usd=0.4,
                       resume=resume == "1", crash_at=None if crash_at == "-" else crash_at, validate=fake_validate,
                       preflight=lambda: (True, "ok"), env_preflight=lambda name: (True, "ok"), root=root, red=fake_red)
    return 0 if r["status"] == dt.DRAFTED else 1


def _script_reply(name, args, id):
    return {"tool_calls": [{"name": name, "args": args, "id": id}], "usage": {"input_tokens": 500, "output_tokens": 60}}


def _spawn(tmp_path, root, crash_at, resume):
    env = {**os.environ, "ARGUS_FAKE_SCRIPT": str(tmp_path / "script.json"),
           "ARGUS_TEST_VALIDATE_LOG": str(tmp_path / "validate.log")}
    return subprocess.run([sys.executable, "-c", PROC, str(ROOT), str(root), str(tmp_path / "runs"), crash_at,
                           resume], cwd=ROOT, capture_output=True, text=True, env=env, timeout=300)


@pytest.mark.parametrize("point, model_calls, checks", [
    ("setup@after_copy", 2, 2),
    ("drafter@after_llm", 2, 2),                  # step 0 was not committed: it is bought again (the script submits)
    ("drafter@after_tool:ReadFile", 2, 2),
    ("drafter@after_tool:SubmitDraft", 2, 4),     # the check ran, its result was not committed: it runs again
    ("draft@after_commit", 2, 2),
    ("finalize@after_write", 2, 2),
])
def test_a_crash_anywhere_resumes_without_redoing_what_was_committed(root, tmp_path, point, model_calls, checks):
    script = [_script_reply("ReadFile", {"path": "src/shop.py"}, "r1"), _script_reply("SubmitDraft", ARGS, "s1"),
              _script_reply("SubmitDraft", ARGS, "s2")]           # a spare, for the call bought again
    (tmp_path / "script.json").write_text(json.dumps(script))
    r1 = _spawn(tmp_path, root, point, "0")
    assert r1.returncode == 42, (r1.stdout[-2000:], r1.stderr[-2000:])
    r2 = _spawn(tmp_path, root, "-", "1")
    assert r2.returncode == 0, (r2.stdout[-2000:], r2.stderr[-2000:])
    d = tmp_path / "runs" / "rc"
    result = json.loads((d / "result.json").read_text())
    assert result["status"] == dt.DRAFTED and (d / "draft.json").exists() and (d / "DRAFT_REVIEW.md").exists()
    evs = events(d)
    i = next(n for n, e in enumerate(evs) if e["event"] == "crash_simulated")
    before, after = evs[:i], evs[i:]
    llm = {e["step"] for e in before if e["event"] == "step_committed" and e["kind"] == "llm"}
    called = {e["step"] for e in after if e["event"] == "llm_call" and e.get("status") == "ok"}
    assert not llm & called, llm & called
    tools = {(e["step"], e["tool"]) for e in before if e["event"] == "step_committed" and e["kind"] == "tool"}
    rerun = {(e["step"], e["tool"]) for e in after if e["event"] == "step_committed" and e["kind"] == "tool"}
    assert not tools & rerun, tools & rerun
    nodes = {e["node"] for e in before if e["event"] == "result_committed"}
    assert not nodes & {e["node"] for e in after if e["event"] == "node_start"}
    assert len([e for e in evs if e["event"] == "llm_call" and e.get("status") == "ok"]) == model_calls
    assert len((tmp_path / "validate.log").read_text().splitlines()) == checks
    redrafted = any(e["event"] == "node_start" and e["node"] == "draft" for e in after)
    if redrafted and any(e["event"] == "llm_call" for e in before):   # the resumed loop starts with what was spent
        restored = [e for e in after if e["event"] == "reservation_restored" and e["node"] == "drafter"]
        assert restored and restored[0]["calls"] >= 1, restored


def test_a_crash_after_a_revision_resumes_from_the_draft_it_revised(root, tmp_path):
    """The arguments a ReviseDraft starts from come from the committed record of the submit before it, so a resumed
    loop revises the same draft (were they lost, the revision would be refused as having nothing to revise)."""
    script = [_script_reply("SubmitDraft", args_with(GREEN_TEST), "s1"),
              _script_reply("ReviseDraft", {"new_tests": ARGS["new_tests"]}, "v1")]
    (tmp_path / "script.json").write_text(json.dumps(script))
    r1 = _spawn(tmp_path, root, "drafter@after_tool:ReviseDraft", "0")
    assert r1.returncode == 42, (r1.stdout[-2000:], r1.stderr[-2000:])
    r2 = _spawn(tmp_path, root, "-", "1")
    assert r2.returncode == 0, (r2.stdout[-2000:], r2.stderr[-2000:])
    d = tmp_path / "runs" / "rc"
    assert json.loads((d / "result.json").read_text())["drafting"]["submits"] == 2
    want, _ = dt.draft_from_args(ARGS, base="shop", policy=POLICY)
    assert json.loads((d / "draft.json").read_text()) == want
    assert len((tmp_path / "validate.log").read_text().splitlines()) == 6      # submit, revision, revision again


def test_the_drafter_is_offered_the_read_tools_of_its_allowlist_and_both_submit_tools():
    names = [t.__name__ for t in dt.offered({"list_files", "search_files", "read_file", "write_file"})]
    assert names == ["ListFiles", "SearchFiles", "ReadFile", "SubmitDraft", "ReviseDraft"]
    assert [t.__name__ for t in dt.offered({"read_file"})] == ["ReadFile", "SubmitDraft", "ReviseDraft"]


def test_the_task_names_each_profile_with_its_limits_and_the_draft_must_choose_one(root, tmp_path):
    r, model, d = run(root, tmp_path, [SUBMIT])
    prompt = model.calls[0]["messages"][1].content
    c = load_config()
    assert "budget_profile, required" in prompt and c["drafter"]["agent_profiles"] == ["default", "large_usd"]
    for name in c["drafter"]["agent_profiles"]:
        p = c["code_task"]["profiles"][name]
        assert f"  - {name}: " in prompt and f"output up to {p['max_output_tokens']:,} per call" in prompt
    assert "  - large: " not in prompt                                         # not offered (router pilot #1)
    assert "$0.45 per attempt, input up to 40,000 per call" in prompt                 # large_usd, in USD
    assert "every file it has read is paid again at every later step" in prompt
    assert json.loads((d / "draft.json").read_text())["contract"]["budget_profile"] == "large_usd"
    assert "Budget profile for the agent: `large_usd`" in (d / "DRAFT_REVIEW.md").read_text()


def test_a_directory_glob_is_refused_at_submit_and_the_drafter_fixes_it_with_revise(root, tmp_path, vlog):
    folder = call("SubmitDraft", dict(ARGS, scope={"writable": ["src/shop.py"],
                                                   "protected": ["tests", "tests/**", "conftest.py"]}), "s0")
    fixed = call("ReviseDraft", {"scope": ARGS["scope"]}, "s1")
    r, model, d = run(root, tmp_path, [folder, fixed])
    seen = tool_texts(model, 1)[0]
    assert "protected glob 'tests' matches no input file (it names a directory; globs match files: use 'tests/**')" \
        in seen
    assert r["status"] == dt.DRAFTED and vlog() == ["target", "regression"]       # the refused one ran nothing
    assert "not `tests`" in dt.SYSTEM


def test_a_profile_not_offered_to_the_drafter_is_refused(root, tmp_path, vlog):
    r, model, d = run(root, tmp_path, [call("SubmitDraft", dict(ARGS, budget_profile="large"), "s0"), SUBMIT])
    assert "budget_profile is required and must be one of ['default', 'large_usd']" in tool_texts(model, 1)[0]
    assert r["status"] == dt.DRAFTED and len(vlog()) == 2                     # the refused one ran nothing



def tiny(**drafter):
    """A config with a profile whose output cannot hold even src/shop.py (63 bytes, about 15 tokens)."""
    c = cfg(**drafter)
    c["code_task"]["profiles"]["tiny"] = {"attempt_tokens": 30000, "max_output_tokens": 5}
    c["drafter"]["agent_profiles"].append("tiny")
    return c


def test_a_writable_file_too_large_to_rewrite_in_one_call_is_refused_without_edit_file(root, tmp_path, vlog):
    small = call("SubmitDraft", dict(ARGS, budget_profile="tiny"), "s0")
    edit = revise({"tools": ["edit_file"]})
    r, model, d = run(root, tmp_path, [small, edit], config=tiny())
    seen = tool_texts(model, 1)[0]
    assert "src/shop.py is 63 bytes (about 15 tokens): without edit_file" in seen and "profile 'tiny' (5 tokens)" in seen
    assert r["status"] == dt.DRAFTED and len(vlog()) == 2                     # the first submit ran nothing
    c = json.loads((d / "draft.json").read_text())["contract"]
    assert c["tools"] == ["edit_file"] and c["budget_profile"] == "tiny"
    assert "Tools added for the agent: `edit_file`" in (d / "DRAFT_REVIEW.md").read_text()


def test_a_file_that_fits_one_call_needs_no_edit_file(root, tmp_path, vlog):
    r, model, d = run(root, tmp_path, [SUBMIT])                               # large_usd: 8,192 tokens of output
    assert r["status"] == dt.DRAFTED and "tools" not in json.loads((d / "draft.json").read_text())["contract"]
    assert "Tools added for the agent: none" in (d / "DRAFT_REVIEW.md").read_text()


def test_the_task_names_the_agents_tools_and_what_may_be_added(root, tmp_path):
    r, model, d = run(root, tmp_path, [SUBMIT])
    prompt = model.calls[0]["messages"][1].content
    assert "The agent's tools: ListFiles, ReadFile, WriteFile, RunValidation. WriteFile replaces a whole file" in prompt
    assert "`tools` may add edit_file and search_files" in prompt


def test_the_harness_puts_the_tools_into_the_contract():
    draft, problems = dt.draft_from_args(dict(ARGS, tools=["search_files", "edit_file"]), base="shop", policy=POLICY)
    assert problems == [] and draft["contract"]["tools"] == ["search_files", "edit_file"]


def test_the_drafter_is_told_what_the_sandbox_lacks_and_only_a_passing_new_test_brings_the_hint(root, tmp_path):
    bad = call("SubmitDraft", args_with(base="other"), "s0")
    r, model, d = run(root, tmp_path, [bad, SUBMIT])
    system = model.calls[0]["messages"][0].content
    assert "no git, no network" in system and "verification/" in system
    assert dt.PASSING_HINT not in tool_texts(model, 1)[0]                   # another problem: no hint



def test_halfway_the_drafter_is_told_how_many_steps_are_left(root, tmp_path):
    reads = [call("ReadFile", {"path": "src/shop.py"}, f"r{i}") for i in range(4)]
    r, model, _ = run(root, tmp_path, reads + [SUBMIT], config=cfg(max_steps=6))
    note = dt.STEPS_LEFT_NOTE.format(n=3, max=6)
    seen = [[m.content for m in c["messages"] if type(m).__name__ == "HumanMessage"] for c in model.calls]
    assert [note in s for s in seen] == [False, False, False, True, True]  # from step 3 = 6 // 2 on, once
    assert seen[4].count(note) == 1 and r["status"] == dt.DRAFTED


def test_the_last_steps_offer_only_the_submit_tools_and_refuse_any_other(root, tmp_path, vlog, monkeypatch):
    offered = []                                       # the tools bound for each model call, in order
    real = StrictScriptedChatModel.bind_tools

    def recording(self, tools, tool_choice=None, **kw):
        offered.append(sorted(t.__name__ for t in tools))
        return real(self, tools, tool_choice=tool_choice, **kw)
    monkeypatch.setattr(StrictScriptedChatModel, "bind_tools", recording)
    reads = [call("ReadFile", {"path": "src/shop.py"}, f"r{i}") for i in range(5)]       # steps 0-4
    late = call("ReadFile", {"path": "src/shop.py"}, "late")                                 # step 5: final
    r, model, d = run(root, tmp_path, reads + [late, SUBMIT], config=cfg(max_steps=8))
    assert dt.final_from(8) == 5 and len(offered) == len(model.calls) == 7
    assert offered[4] == ["ListFiles", "ReadFile", "ReviseDraft", "SearchFiles", "SubmitDraft"]
    assert offered[5] == offered[6] == ["ReviseDraft", "SubmitDraft"]
    final_note = dt.FINAL_NOTE.format(n=dt.FINAL_STEPS)
    assert final_note in [m.content for m in model.calls[5]["messages"]]
    assert final_note not in [m.content for m in model.calls[4]["messages"]]
    assert tool_texts(model, 6)[-1].startswith("Refused: ReadFile is not offered in the last 3 steps")
    assert r["status"] == dt.DRAFTED and vlog() == ["target", "regression"]


def test_too_few_steps_have_no_final_restriction():
    assert dt.final_from(6) == 6 and dt.final_from(7) == 4


def test_the_steps_left_note_survives_a_resume(root, tmp_path):
    """The note is part of the conversation the step keys hash: a resumed run rebuilds it and replays its steps."""
    reads = [call("ReadFile", {"path": "src/shop.py"}, f"r{i}") for i in range(3)]
    c = cfg(max_steps=6)
    r1, _, d = run(root, tmp_path, reads + [SUBMIT], config=c)
    model = StrictScriptedChatModel(script=[])
    r2 = dt.run_drafter(run_id="d", runs_dir=tmp_path / "runs", cfg=c, resume=True, models={"drafter": model},
                        validate=fake_validate, preflight=lambda: (True, "ok"), env_preflight=lambda name: (True, "ok"),
                        root=root, red=fake_red)
    assert model.calls == [] and r2["status"] == r1["status"] == dt.DRAFTED


def test_the_drafter_reads_up_to_200000_input_tokens_per_call():
    c = load_config()
    assert dt.drafter_settings(dict(c, budget=dict(c["budget"], max_usd=0.75)))["max_input_tokens"] == 200000
