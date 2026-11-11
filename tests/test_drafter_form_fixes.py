"""SPEC_DRAFTER_FORM_FIXES: the harness corrects the draft's form slips before the draft is built and checked (P1 ids, P2
new tests protected, P3 protected globs that protect nothing), says so, and the next ReviseDraft starts from the
corrected draft; P4 a required old test that did not run is named in full."""
import copy

import pytest

from acceptance import draft as dr
from acceptance import validation as av
from codetask import drafter as cdr

BASE = {"src/sum.js": "x", "src/sum.test.js": "x", "src/neg.test.js": "x"}
NEW = "src/clamp.test.js"


def args(ids=("target",), protected=("src/*.test.js",), writable=("src/sum.js",), new=NEW):
    return {"plan": {"files": ["src/sum.js"], "steps": ["s"], "risks": ["r"]},
            "scope": {"writable": list(writable), "protected": list(protected)},
            "validation": [{"id": i, "paths": [NEW], "must_pass": [f"{NEW}::floors at 0"], "min_tests": 1}
                           for i in ids],
            "new_tests": [{"path": new, "content": "x"}], "unverifiable": [], "budget_profile": "default",
            "tools": ["edit_file"]}


@pytest.mark.parametrize("given, want", [("Target", "target"), ("jobs-a", "jobs_a"), ("1st", "v_1st"),
                                         ("Old Tests.v2", "old_tests_v2"), ("x" * 40, "x" * 32),
                                         ("é-ok", "v___ok")])
def test_p1_an_id_the_contract_refuses_is_rewritten_as_one_it_takes(given, want):
    out, changes = cdr.normalize_args(args(ids=(given,)), BASE)
    assert out["validation"][0]["id"] == want and cdr.ct.ID.match(want)
    assert changes == [f"validation id {given!r} is now {want!r}"]


def test_p1_a_good_id_a_taken_one_and_one_that_is_no_text_are_left():
    out, changes = cdr.normalize_args(args(ids=("target", "Target", "ok_2")), BASE)
    assert [v["id"] for v in out["validation"]] == ["target", "Target", "ok_2"] and changes == []
    a = args()
    a["validation"][0]["id"] = ["x"]
    out, changes = cdr.normalize_args(a, BASE)
    assert out["validation"][0]["id"] == ["x"] and changes == []


def test_p2_a_new_test_no_glob_protects_is_protected_and_one_already_protected_is_not_added():
    out, changes = cdr.normalize_args(args(protected=("src/sum.test.js",)), BASE)
    assert out["scope"]["protected"] == ["src/sum.test.js", NEW] and changes == [f"new test {NEW} is now protected"]
    out, changes = cdr.normalize_args(args(), BASE)
    assert out["scope"]["protected"] == ["src/*.test.js"] and changes == []


def test_p2_a_new_test_writable_is_still_refused_by_the_check():
    out, _ = cdr.normalize_args(args(writable=("src/*.js",), protected=("src/sum.test.js",)), BASE)
    assert out["scope"]["writable"] == ["src/*.js"] and NEW in out["scope"]["protected"]


def test_p3_globs_that_protect_nothing_are_dropped_and_the_others_kept():
    globs = ("src/*.test.js", "src/**/*.test.ts", "package-lock.json", "src/clamp.test.js", "src")
    out, changes = cdr.normalize_args(args(protected=globs), BASE)
    assert out["scope"]["protected"] == ["src/*.test.js", "src/clamp.test.js", "src"]     # a directory: the check says
    assert changes == ["protected glob 'src/**/*.test.ts' matched no file and was dropped",
                       "protected glob 'package-lock.json' matched no file and was dropped"]


def test_the_arguments_given_are_never_changed_in_place():
    a = args(ids=("Target",), protected=("x/*.js",))
    before = copy.deepcopy(a)
    cdr.normalize_args(a, BASE)
    assert a == before


@pytest.mark.parametrize("bad", [None, "x", [], {"scope": "s"}, {"scope": {"protected": ["a", 1]}},
                                 {"validation": "v", "new_tests": "n"}])
def test_other_shapes_are_left_for_the_checks(bad):
    assert cdr.normalize_args(bad, BASE) == (bad, [])


class Log:
    def __init__(self):
        self.events = []

    def emit(self, event, **kw):
        self.events.append((event, kw))


POLICY = {"environment": "pwa_node22", "runner": "vitest", "validation_timeout_s": 120, "profiles": ["default"],
          "max_submits": 5}


def make(tmp_path, monkeypatch, report=None):
    intake_dir = tmp_path / "fixtures" / "repos" / "sums"
    for p, text in BASE.items():
        (intake_dir / p).parent.mkdir(parents=True, exist_ok=True)
        (intake_dir / p).write_text(text)
    checked = []

    def check(draft, **kw):
        checked.append(copy.deepcopy(draft))
        return report or {"problems": ["stop here"], "baseline": None}
    monkeypatch.setattr(cdr.dr, "check", check)
    log = Log()
    submit = cdr.make_submit(inputs={"intake": "sums", "issue": "i"}, policy=POLICY, scfg={}, root=tmp_path, log=log,
                             validate=None, source=intake_dir)
    return submit, checked, log


def test_the_checked_draft_is_the_corrected_one_and_the_reply_and_the_log_say_what_changed(tmp_path, monkeypatch):
    submit, checked, log = make(tmp_path, monkeypatch)
    r = submit(args(ids=("Target",), protected=("src/sum.test.js", "src/**/*.test.ts")), 1)
    c = checked[0]["contract"]
    assert [v["id"] for v in c["validation"]][0] == "target"
    assert c["scope"]["protected"] == ["src/sum.test.js", NEW]
    said = ("The harness changed your draft (ReviseDraft starts from the changed one): validation id 'Target' is now "
            f"'target'; new test {NEW} is now protected; protected glob 'src/**/*.test.ts' matched no file and was "
            "dropped.")
    assert said in r["content"] and r["content"].startswith("Draft rejected (submit 1 of 5)")
    assert ("draft_normalized", {"submit": 1, "changes": [
        "validation id 'Target' is now 'target'", f"new test {NEW} is now protected",
        "protected glob 'src/**/*.test.ts' matched no file and was dropped"]}) in log.events
    assert r["args"]["validation"][0]["id"] == "target"           # ReviseDraft starts from the corrected arguments
    again = submit({"unverifiable": ["u"]}, 2, last=r["args"], revise=True)
    assert again["args"]["scope"]["protected"] == ["src/sum.test.js", NEW] and NORMALIZED_NOT_IN(again)


def NORMALIZED_NOT_IN(r):
    return cdr.NORMALIZED not in r["content"]


def test_an_accepted_draft_says_what_changed_too(tmp_path, monkeypatch):
    submit, _, _ = make(tmp_path, monkeypatch, report={"problems": [], "baseline": None})
    monkeypatch.setattr(cdr, "swallowed_problems", lambda d, r: [])
    monkeypatch.setattr(cdr, "call_path_outside", lambda d, r: [])
    r = submit(args(ids=("Target",)), 1)
    assert r["finished"] and r["content"].startswith(cdr.ACCEPTED) and "validation id 'Target' is now" in r["content"]


def test_p4_an_old_test_that_did_not_run_is_named_in_full():
    spec = {"id": "near", "executable": "vitest", "args": ["run", "src/a.test.jsx"], "timeout_s": 60, "min_tests": 1,
            "max_skipped": 0, "must_pass": ["src/a.test.jsx::empties the box"], "environment": "pwa_node22"}
    ev = {}
    av._named_like_evidence(ev, {"src/a.test.jsx::empties the box": None},
                            {"tests": {"src/a.test.jsx::clearing > empties the box": "ok"}})
    assert ev == {"named_like": {"src/a.test.jsx::empties the box":
                                 " (ran under the full name: src/a.test.jsx::clearing > empties the box)"}}
    nothing = {}
    av._named_like_evidence(nothing, {"src/a.test.jsx::x": None, "src/a.test.jsx::y": "ok"}, {"tests": {}})
    assert nothing == {}
    assert spec["must_pass"]


def test_p4_the_draft_check_quotes_the_full_name(tmp_path):
    old, new = "src/a.test.jsx::empties the box", "src/n.test.jsx::new"
    spec = {"id": "near", "executable": "vitest", "args": ["run", "src/a.test.jsx", "src/n.test.jsx"], "timeout_s": 60,
            "min_tests": 1, "max_skipped": 0, "must_pass": [old, new], "environment": "pwa_node22"}
    hint = " (ran under the full name: src/a.test.jsx::clearing > empties the box)"

    def validate(spec, ws, cfg):
        return {"status": "fail", "evidence": {"must_pass": {old: None, new: "FAIL"}, "failures": 1, "errors": 0,
                                               "consistent": True, "named_like": {old: hint}}}
    problems, _ = dr.baseline_problems({"validation": [spec]}, {"src/n.test.jsx"}, tmp_path, {}, validate=validate)
    assert f"existing test {old} must pass on the baseline, is None{hint}" in problems


def test_the_submit_tools_moved_to_version_5():
    import inspect
    src = inspect.getsource(cdr.build_graph)
    assert '"SubmitDraft": f"5:' in src and '"ReviseDraft": f"5:' in src
