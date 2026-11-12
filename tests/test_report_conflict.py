"""SPEC_REPORT_CONFLICT v1-v3 (the MVP): the agent's way out when old protected tests contradict its change, the harness's own
check of the report, the order of decisions in acceptance, and what the human is told. Scripted model, injected validation
and red check: no Docker."""
import copy
import json
import sqlite3
import sys
from pathlib import Path

import pytest

from acceptance import conflict as cf
from acceptance import contract as ct
from acceptance.workspace import snapshot
from codetask import status as st
from codetask import tools as tl
from codetask.agent import feedback_from, rejected_reply, system_prompt, task_prompt
from codetask.run import run_code_task
from models.fake import StrictScriptedChatModel, reply
from runner import load_config

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="the path jail needs openat; the VM runs these")

OLD_NODE, NEW_NODE = "tests/test_old.py::test_old", "tests/test_new.py::test_new"
FILES = {"src/app.py": "BEHAVIOUR = 'old'\n",
         "tests/test_old.py": "from src.app import BEHAVIOUR\n\n\ndef test_old():\n    assert BEHAVIOUR == 'old'\n",
         "tests/test_new.py": "from src.app import BEHAVIOUR\n\n\ndef test_new():\n    assert BEHAVIOUR == 'new'\n",
         "conftest.py": ""}
CONTRACT = {"contract": "app_fix", "version": 1,
            "inputs": {"workspace": "fixtures/repos/app", "issue": "BEHAVIOUR must be 'new'."},
            "scope": {"writable": ["src/**"], "protected": ["tests/**", "conftest.py"]},
            "artifacts": [{"path": "SUMMARY.json", "type": "json", "schema": "claims_v2"}],
            "validation": [{"id": "unit", "executable": "python", "args": ["-m", "pytest", "tests"], "timeout_s": 60,
                            "min_tests": 2, "max_skipped": 0, "must_pass": [NEW_NODE]}],
            "judge": [], "limits": {"max_usd": 1.0, "max_iterations": 3}}


def cfg():
    c = load_config()
    c["roles"]["coder"]["model"] = "fake:scripted"
    return c


def call(name, args, id):
    return reply(tool_calls=[{"name": name, "args": args, "id": id}], input_tokens=500, output_tokens=60)


WRITE_NEW = call("WriteFile", {"path": "src/app.py", "content": "BEHAVIOUR = 'new'\n"}, "w1")
WRITE_BOTH = call("WriteFile", {"path": "src/app.py", "content": "OLD = 'old'\nNEW = 'new'\n"}, "w2")
REPORT = call("ReportConflict", {"files": ["tests/test_old.py"]}, "c1")
REPORT_AGAIN = call("ReportConflict", {"files": ["tests/test_old.py"]}, "c2")
REPORT_WRONG = call("ReportConflict", {"files": ["tests/test_new.py"]}, "c3")
FINISH = call("Finish", {"claims": [], "summary": "done"}, "f1")


def make_root(tmp_path):
    root = tmp_path / "root"
    for rel, text in FILES.items():
        p = root / "fixtures" / "repos" / "app" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return root


def fake_validate(spec, workspace, sandbox_cfg, log=None):
    """pytest-shaped evidence: the old test is red once the code says 'new' only, the new test is red while it says 'old' only."""
    text = (Path(workspace) / "src" / "app.py").read_text()
    red = ([OLD_NODE] if "'old'" not in text else []) + ([NEW_NODE] if "'new'" not in text else [])
    must = {t: "FAIL" if t in red else "ok" for t in spec.get("must_pass", [])}
    return {"id": f"validation:{spec['id']}", "layer": "C", "status": "fail" if red else "pass",
            "reason": "pytest outcome FAILED" if red else "",
            "evidence": {"runner": "pytest", "consistent": True, "tests_run": 2, "failures": len(red), "errors": 0,
                         "timed_out": False, "killed": False, "output_limit_exceeded": False, "truncated": False,
                         "skipped": 0, "must_pass": must, "failed_nodes": red, "output_tail": ""}}


class Red:
    """The harness's red check, from the text of src/app.py in the directory it is given."""
    def __init__(self, fail=None):
        self.calls, self.fail = [], fail

    def __call__(self, nodes, workdir, sandbox_cfg, **kw):
        self.calls.append((list(nodes), Path(workdir).name))
        if self.fail:
            return self.fail(len(self.calls))
        text = (Path(workdir) / "src" / "app.py").read_text()
        out = {}
        for n in nodes:
            ok = ("'old'" if n == OLD_NODE else "'new'") in text
            out[n] = {"outcome": "passed" if ok else "failed", "type": None if ok else "builtins.AssertionError",
                      "assertion": not ok, "path": None if ok else n.split("::")[0]}
        return out, None, False


def run(tmp_path, script, *, red=None, validate=fake_validate, max_iterations=3, run_id="t", initial_conflict=None):
    root = make_root(tmp_path)
    contract = copy.deepcopy(CONTRACT)
    contract["limits"]["max_iterations"] = max_iterations
    assert ct.validate(contract) == []
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(contract), encoding="utf-8")
    model = StrictScriptedChatModel(script=list(script))
    red = red or Red()
    r = run_code_task(contract_path=path, run_id=run_id, runs_dir=tmp_path / "runs", cfg=cfg(), models={"coder": model},
                      validate=validate, preflight=lambda: (True, "ok"), env_preflight=lambda n: (True, "ok"), root=root,
                      red=red, initial_conflict=initial_conflict)
    return r, model, tmp_path / "runs" / run_id, red


def verdict(d, i=0):
    return json.loads((d / f"verdict_{i}.json").read_text(encoding="utf-8"))


def tool_answer(model, call_id):
    """The text the model was given for the tool call `call_id`, in the last request that carried it."""
    for c in reversed(model.calls):
        for m in c["messages"]:
            if getattr(m, "tool_call_id", None) == call_id:
                return m.content
    return None


# ---- the tool -------------------------------------------------------------------------------------------------------

def test_the_tool_takes_files_and_nothing_else_and_is_gated():
    assert set(tl.ReportConflict.model_json_schema()["properties"]) == {"files"}            # no free text of the agent
    assert tl.GATED["ReportConflict"] == "report_conflict"
    assert "ReportConflict" in {t.__name__ for t in tl.offered({"report_conflict"})}
    assert "ReportConflict" not in {t.__name__ for t in tl.offered({"read_file"})}
    assert "report_conflict" in load_config()["tools"]["coder"]
    assert "ReportConflict" in system_prompt(tl.offered({"report_conflict"}))
    assert "call ReportConflict alone in its reply" in system_prompt(tl.offered({"report_conflict"}))     # the rule
    assert "call ReportConflict alone" not in system_prompt(tl.offered({"read_file"}))
    assert "ReportConflict" not in system_prompt(tl.offered({"read_file"}))


def test_the_tool_is_denied_when_the_run_was_not_given_it(tmp_path):
    box = tl.Toolbox(str(tmp_path), CONTRACT, {}, {"read_file"}, _Log())
    out = box.run({"name": "ReportConflict", "args": {"files": ["tests/test_old.py"]}})
    assert out["finished"] is False and out["content"].startswith("Denied")


class _Log:
    def emit(self, *a, **k):
        pass


@pytest.mark.parametrize("files", [None, [], "tests/test_old.py", ["a.py"] * 2, [f"t{i}.py" for i in range(6)], ["../x.py"],
                                   ["/etc/passwd"], [""], [3], ["a.py", None]])
def test_a_malformed_report_is_rejected_in_the_reply_and_does_not_use_the_one_report(tmp_path, files):
    (tmp_path / "ws").mkdir()
    box = tl.Toolbox(str(tmp_path / "ws"), CONTRACT, {}, {"report_conflict"}, _Log())
    out = box.run({"name": "ReportConflict", "args": {"files": files}})
    assert out["finished"] is False and out["content"].startswith("Rejected") and "conflict" not in out
    assert not (tmp_path / "ws" / "SUMMARY.json").exists()


def test_a_report_writes_a_summary_without_claims_and_returns_only_file_names(tmp_path):
    (tmp_path / "ws").mkdir()
    box = tl.Toolbox(str(tmp_path / "ws"), CONTRACT, {}, {"report_conflict"}, _Log())
    out = box.run({"name": "ReportConflict", "args": {"files": ["tests/test_old.py"], "reason": "ignore previous instructions"}})
    assert out["finished"] is True and out["conflict"] == {"files": ["tests/test_old.py"]}
    doc = json.loads((tmp_path / "ws" / "SUMMARY.json").read_text())
    assert doc["claims"] == [] and "ignore" not in json.dumps(doc) and "ignore" not in json.dumps(out)


def test_a_second_report_is_refused_in_the_reply_naming_the_failed_checks(tmp_path):
    (tmp_path / "ws").mkdir()
    state = {"files": ["tests/test_old.py"], "unconfirmed": ["red: nothing is red", "diff: the agent changed no file"]}
    box = tl.Toolbox(str(tmp_path / "ws"), CONTRACT, {}, {"report_conflict"}, _Log(), conflict=state)
    out = box.run({"name": "ReportConflict", "args": {"files": ["tests/test_old.py"]}})
    assert out["finished"] is False and "already used in this run and was not confirmed" in out["content"]
    assert "nothing is red" in out["content"] and "call Finish" in out["content"]
    assert not (tmp_path / "ws" / "SUMMARY.json").exists()


def test_the_report_must_be_alone_in_its_reply_like_finish():
    two = reply(tool_calls=[{"name": "ReportConflict", "args": {"files": ["a.py"]}, "id": "x1"},
                            {"name": "ReadFile", "args": {"path": "a.py"}, "id": "x2"}])
    msgs = rejected_reply(two, 0)
    assert len(msgs) == 2 and "ReportConflict must be the only tool call" in msgs[0].content
    both = reply(tool_calls=[{"name": "Finish", "args": {}, "id": "y1"}, {"name": "ReportConflict", "args": {}, "id": "y2"}])
    assert "Finish must be the only tool call" in rejected_reply(both, 0)[0].content        # Finish's wording is unchanged


# ---- a confirmed report ----------------------------------------------------------------------------------------------

def test_a_confirmed_report_ends_the_run_blocked_test_conflict_with_the_files_and_the_nodes(tmp_path):
    r, model, d, red = run(tmp_path, [WRITE_NEW, REPORT])
    assert r["status"] == st.BLOCKED and r["blocked_reason"] == "test_conflict" and r["attempts"] == 1
    assert r["attempt"]["end"] == "conflict_reported" and r["attempt"]["conflict"] == {"files": ["tests/test_old.py"]}
    c = verdict(d)["conflict"]
    assert c["state"] == "confirmed" and c["files"] == ["tests/test_old.py"]
    assert c["nodes"] == [{"file": "tests/test_old.py", "node": OLD_NODE, "type": "builtins.AssertionError",
                           "path": "tests/test_old.py"}]
    assert r["verdict"]["conflict"]["state"] == "confirmed"
    assert "tests/test_old.py" in r["stop_reason"]
    assert len(model.calls) == 2                                                          # no further attempt
    assert [n[1] for n in red.calls] == ["app", "workspace", "workspace"]                 # input once, workspace twice
    assert json.loads((d / "workspace" / "SUMMARY.json").read_text())["claims"] == []
    assert "test_conflict" in st.BLOCKED_REASONS


def test_a_confirmed_report_is_never_a_pass_and_the_old_tests_stay_untouched(tmp_path):
    r, model, d, red = run(tmp_path, [WRITE_NEW, REPORT])
    assert r["status"] != st.DONE
    assert (d / "workspace" / "tests" / "test_old.py").read_text() == FILES["tests/test_old.py"]
    assert (make_root(tmp_path) / "fixtures/repos/app/src/app.py").read_text() == FILES["src/app.py"]      # the input


def test_a_confirmed_report_wins_over_max_iterations_and_stagnation(tmp_path):
    r, model, d, red = run(tmp_path, [WRITE_NEW, REPORT], max_iterations=1)
    assert r["status"] == st.BLOCKED and r["blocked_reason"] == "test_conflict"           # not FAILED_ACCEPTANCE/max_iterations
    r, model, d, red = run(tmp_path / "s", [FINISH, FINISH, WRITE_NEW, REPORT], max_iterations=5)
    assert r["status"] == st.FAILED_ACCEPTANCE and r["stop_reason"].startswith("stagnant")   # two bare failures stagnate first
    r, model, d, red = run(tmp_path / "t", [WRITE_NEW, FINISH, REPORT], max_iterations=3)    # one failure, then the report
    assert r["status"] == st.BLOCKED and r["blocked_reason"] == "test_conflict" and r["attempts"] == 2


# ---- a report the harness cannot confirm -------------------------------------------------------------------------------

def test_an_unconfirmed_report_fails_the_attempt_and_the_run_goes_on_with_the_findings(tmp_path):
    r, model, d, red = run(tmp_path, [WRITE_NEW, REPORT_WRONG, WRITE_BOTH, FINISH])
    c = verdict(d, 0)["conflict"]
    assert c["state"] == "unconfirmed" and any("named" in x for x in c["unconfirmed"])
    assert r["status"] == st.DONE and r["attempts"] == 2
    second = model.calls[2]["messages"][1].content
    assert "You reported a conflict with these old tests and the harness did not confirm it: tests/test_new.py" in second
    assert "ReportConflict is not available again in this run" in second
    assert red.calls == []                                                                  # no sandbox for a static miss


def test_a_second_report_in_the_run_is_refused_in_the_reply_and_the_run_goes_on(tmp_path):
    r, model, d, red = run(tmp_path, [WRITE_NEW, REPORT_WRONG, REPORT_AGAIN, WRITE_BOTH, FINISH])
    answer = tool_answer(model, "c2")
    assert answer.startswith("Refused: ReportConflict was already used in this run and was not confirmed")
    assert r["status"] == st.DONE                       # the refusal ended nothing: the next calls ran


def test_an_unconfirmed_report_on_the_last_iteration_is_a_failed_acceptance(tmp_path):
    r, model, d, red = run(tmp_path, [WRITE_NEW, REPORT_WRONG], max_iterations=1)
    assert r["status"] == st.FAILED_ACCEPTANCE and r["stop_reason"] == "max_iterations"
    assert verdict(d)["conflict"]["state"] == "unconfirmed" and r["verdict"]["conflict"]["state"] == "unconfirmed"
    assert r["conflict"]["files"] == ["tests/test_new.py"] and r["conflict"]["unconfirmed"]      # the state the run ended with


def test_a_report_when_every_criterion_passes_is_done_with_a_note_in_the_verdict(tmp_path):
    r, model, d, red = run(tmp_path, [WRITE_BOTH, REPORT])
    assert r["status"] == st.DONE
    c = verdict(d)["conflict"]
    assert c["state"] == "unconfirmed" and "nothing is red" in c["unconfirmed"][0]
    assert red.calls == []


def test_the_files_come_from_the_committed_result_summary_json_never_holds_them(tmp_path):
    r, model, d, red = run(tmp_path, [WRITE_NEW, REPORT])
    doc = json.loads((d / "workspace" / "SUMMARY.json").read_text())
    assert "tests/test_old.py" not in json.dumps(doc) and "files" not in doc          # nothing there to read them from
    assert verdict(d)["conflict"]["files"] == ["tests/test_old.py"] and r["blocked_reason"] == "test_conflict"


# ---- sandbox trouble is not a miss -------------------------------------------------------------------------------------

@pytest.mark.parametrize("at", [1, 2, 3])
def test_a_missing_sandbox_when_the_report_is_checked_blocks_the_run_and_uses_no_report(tmp_path, at):
    good = Red()

    def fail(n):
        return (None, "sandbox unavailable: docker is down", True) if n == at else good(*good.last)

    class Wrapped(Red):
        def __call__(self, nodes, workdir, sandbox_cfg, **kw):
            n = len(self.calls) + 1
            if n == at:
                self.calls.append((list(nodes), Path(workdir).name))
                return None, "sandbox unavailable: docker is down", True
            return super().__call__(nodes, workdir, sandbox_cfg, **kw)
    r, model, d, red = run(tmp_path, [WRITE_NEW, REPORT], red=Wrapped())
    assert r["status"] == st.BLOCKED and r["blocked_reason"] == "sandbox_unavailable" and "docker is down" in r["stop_reason"]
    assert verdict(d)["conflict"]["state"] == "blocked" and r["attempts"] == 1


def test_an_unreadable_run_counts_as_a_miss_and_uses_the_one_report(tmp_path):
    red = Red(fail=lambda n: (None, "the run timed out or its output was cut", False))
    r, model, d, _ = run(tmp_path, [WRITE_NEW, REPORT, REPORT_AGAIN, WRITE_BOTH, FINISH], red=red)
    assert any("could not be read" in x for x in verdict(d)["conflict"]["unconfirmed"])
    assert tool_answer(model, "c2").startswith("Refused: ReportConflict was already used")


def test_a_failure_inside_the_check_is_a_miss_never_a_confirmation(tmp_path):
    def boom(n):
        raise RuntimeError("bug")
    r, model, d, red = run(tmp_path, [WRITE_NEW, REPORT], red=Red(fail=boom), max_iterations=1)
    assert r["status"] == st.FAILED_ACCEPTANCE and verdict(d)["conflict"]["state"] == "unconfirmed"


# ---- the checks, one by one --------------------------------------------------------------------------------------------

class Case:
    """The inputs of cf.verify for the one conflict of this file, to be broken one way at a time."""
    def __init__(self, tmp_path):
        self.root = make_root(tmp_path)
        self.input_dir = self.root / "fixtures" / "repos" / "app"
        self.ws = tmp_path / "ws"
        import shutil
        shutil.copytree(self.input_dir, self.ws)
        self.before = snapshot(self.ws)
        (self.ws / "src" / "app.py").write_text("BEHAVIOUR = 'new'\n")
        self.contract = copy.deepcopy(CONTRACT)
        self.files = ["tests/test_old.py"]
        self.repo_protected, self.draft_files = (), ()
        self.red = Red()
        self.evidence = None

    def verdict(self):
        v = fake_validate(self.contract["validation"][0], self.ws, {})
        if self.evidence:
            v["evidence"].update(self.evidence)
        crit = [{"id": "scope:protected", "layer": "A", "status": "pass", "reason": "", "evidence": {}},
                {"id": "artifact:SUMMARY.json", "layer": "B", "status": "pass", "reason": "", "evidence": {}},
                v, {"id": "claims", "layer": "D", "status": "pass", "reason": "", "evidence": {}}]
        return {"outcome": "fail", "criteria": crit}

    def verify(self):
        return cf.verify(self.contract, self.verdict(), self.files, ws=self.ws, before=self.before,
                         input_dir=self.input_dir, scfg={}, repo_protected=self.repo_protected,
                         draft_files=self.draft_files, red=self.red)


def test_the_baseline_case_is_confirmed(tmp_path):
    out = Case(tmp_path).verify()
    assert out["state"] == "confirmed" and out["unconfirmed"] == [] and out["nodes"][0]["node"] == OLD_NODE


def breaks(tmp_path, change, word, state="unconfirmed"):
    c = Case(tmp_path)
    change(c)
    out = c.verify()
    assert out["state"] == state, out
    assert any(word in x for x in out["unconfirmed"]) or (state != "unconfirmed" and word in out.get("reason", "")), out
    return out


def test_every_non_validation_criterion_must_pass(tmp_path):
    def change(c):
        c.verdict = (lambda orig: lambda: {**orig(), "criteria": [dict(x, status="fail", reason="boom") if x["id"] == "scope:protected" else x for x in orig()["criteria"]]})(c.verdict)
    breaks(tmp_path, change, "scope:protected did not pass")


@pytest.mark.parametrize("evidence,word", [({"timed_out": True}, "did not finish cleanly"), ({"truncated": True}, "cleanly"),
                                           ({"output_limit_exceeded": True}, "cleanly"), ({"killed": True}, "cleanly"),
                                           ({"consistent": False}, "cleanly"), ({"tests_run": None}, "cleanly"),
                                           ({"runner": "unittest"}, "no per-test records"),
                                           ({"failures": 60}, "too many red tests to enumerate")])
def test_a_validation_that_did_not_finish_cleanly_or_lists_too_few_red_tests_does_not_confirm(tmp_path, evidence, word):
    breaks(tmp_path, lambda c: setattr(c, "evidence", evidence), word)


def test_nothing_red_a_stray_red_test_and_a_quiet_named_file_do_not_confirm(tmp_path):
    breaks(tmp_path / "1", lambda c: (setattr(c, "evidence", {"failed_nodes": [], "failures": 0})), "nothing is red")
    breaks(tmp_path / "2", lambda c: setattr(c, "files", ["tests/test_other.py"]), "a red test is in a file the agent did not name")
    out = breaks(tmp_path / "3", lambda c: setattr(c, "files", ["tests/test_old.py", "tests/test_new.py"]),
                 "a named file has no red test")
    assert "test_new.py" in "".join(out["unconfirmed"])


def test_a_required_test_that_is_neither_red_nor_ok_does_not_confirm(tmp_path):
    breaks(tmp_path, lambda c: setattr(c, "evidence", {"must_pass": {NEW_NODE: "skipped"}}), "required test")


def test_a_run_that_changed_nothing_does_not_confirm(tmp_path):
    def change(c):
        (c.ws / "src" / "app.py").write_text(FILES["src/app.py"])
        (c.ws / "SUMMARY.json").write_text('{"claims": []}')            # the agent always writes it: it is not a change
        c.verdict = (lambda orig: lambda: dict(orig()))(c.verdict)
    # with the old text restored the old test is not red, so also add the red node by hand to isolate the diff check
    breaks(tmp_path, lambda c: (change(c), setattr(c, "evidence", {"failed_nodes": [OLD_NODE], "failures": 1})), "changed no file")


def test_the_old_test_file_must_be_untouched_protected_and_not_the_drafts(tmp_path):
    breaks(tmp_path, lambda c: (c.ws / "tests" / "test_old.py").write_text("# touched\n"), "was changed by the agent")
    breaks(tmp_path / "p", lambda c: c.contract["scope"].update(protected=["conftest.py"]), "is not protected")
    breaks(tmp_path / "d", lambda c: setattr(c, "draft_files", {"tests/test_old.py"}), "added or changed")
    out = Case(tmp_path / "ok")
    out.repo_protected = ("tests/**",)
    out.contract["scope"]["protected"] = []          # protected only by the repository's own list: enough
    assert out.verify()["state"] == "confirmed"


def test_the_baseline_must_pass_on_the_untouched_input(tmp_path):
    def change(c):
        base = c.red

        def red(nodes, workdir, scfg, **kw):
            base.calls.append(1)
            return {n: {"outcome": "failed", "type": "builtins.AssertionError", "assertion": True, "path": "tests/test_old.py"}
                    for n in nodes}, None, False
        c.red = red
    breaks(tmp_path, change, "does not pass on the untouched input")


def test_a_node_that_does_not_fail_in_the_harness_run_or_differs_between_runs_does_not_confirm(tmp_path):
    state = {"n": 0}

    def flaky(c):
        base = c.red

        def red(nodes, workdir, scfg, **kw):
            state["n"] += 1
            out, why, un = base(nodes, workdir, scfg, **kw)
            if state["n"] == 3:
                out = {n: dict(rec, type="builtins.ValueError") for n, rec in out.items()}
            return out, why, un
        c.red = red
    breaks(tmp_path, flaky, "is not stable between two runs")

    def passing(c):
        base = c.red

        def red(nodes, workdir, scfg, **kw):
            out, why, un = base(nodes, workdir, scfg, **kw)
            if Path(workdir).name == "ws":
                out = {n: {"outcome": "passed", "type": None, "assertion": False, "path": None} for n in nodes}
            return out, why, un
        c.red = red
    breaks(tmp_path / "p", passing, "does not fail when the harness runs it")


def test_a_failure_whose_deepest_frame_is_in_production_code_does_not_confirm_but_one_in_a_helper_does(tmp_path):
    def prod(c):
        base = c.red

        def red(nodes, workdir, scfg, **kw):
            out, why, un = base(nodes, workdir, scfg, **kw)
            if Path(workdir).name == "ws":
                out = {n: dict(rec, path="src/app.py") for n, rec in out.items()}
            return out, why, un
        c.red = red
    breaks(tmp_path, prod, "src/app.py was changed by the agent")   # production code: the agent changed it

    def helper(c):                                        # a protected, untouched helper file: the shape of a real conflict
        (c.input_dir / "tests" / "helpers.py").write_text("X = 1\n")
        (c.ws / "tests" / "helpers.py").write_text("X = 1\n")
        c.before = snapshot(c.input_dir)               # the intake: the helper is in it, app.py is not yet changed
        c.contract["scope"]["protected"] = ["tests/**", "conftest.py"]
        base = c.red

        def red(nodes, workdir, scfg, **kw):
            out, why, un = base(nodes, workdir, scfg, **kw)
            return {n: dict(rec, path="tests/helpers.py" if rec["path"] else None) for n, rec in out.items()}, why, un
        c.red = red
    c = Case(tmp_path / "h")
    helper(c)
    assert c.verify()["state"] == "confirmed"


def test_a_missing_record_for_a_node_does_not_confirm(tmp_path):
    def change(c):
        c.red = lambda nodes, workdir, scfg, **kw: ({}, None, False)
    breaks(tmp_path, change, "does not pass on the untouched input")


def test_the_file_list_is_checked_for_shape_by_the_harness_too(tmp_path):
    for bad in (None, [], ["a"] * 2, ["../a.py"], [str(i) for i in range(6)], ["/abs.py"], [1]):
        out = cf.verify(CONTRACT, {"criteria": []}, bad, ws=tmp_path, before={}, input_dir=tmp_path, scfg={}, red=Red())
        assert out["state"] == "unconfirmed" and out["unconfirmed"][0].startswith("files:")
        assert isinstance(out["files"], list)


# ---- the router: status, retry, --not-a-conflict -----------------------------------------------------------------------

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_drafter as td  # noqa: E402
from router import job as rj  # noqa: E402
from test_router import FINISH as ROUTER_FINISH  # noqa: E402
from test_router import WRITE as ROUTER_WRITE  # noqa: E402
from test_router import Env  # noqa: E402

BROKE = td.FIXED + "# BROKE the plain total\n"                      # a "fix" after which the old plain test is red
BROKE_WRITE = call("WriteFile", {"path": "src/shop.py", "content": BROKE}, "wb")
ROUTER_REPORT = call("ReportConflict", {"files": ["tests/test_old.py"]}, "rc1")


def router_validate(spec, workspace, sandbox_cfg, log=None):
    """pytest-shaped evidence for the drafter fixture's two validations: `target` is red until src/shop.py changes, the
    old plain test (validation `regression`) is red when the text says BROKE."""
    text = (Path(workspace) / "src" / "shop.py").read_text()
    statuses = {}
    for path in spec["args"][2:]:
        if path == "tests/test_new.py":
            statuses[td.NEW_NODE] = "FAIL" if text == td.BUGGY else "ok"
        elif path == "tests/test_old.py":
            statuses[td.OLD_NODE] = "FAIL" if "BROKE" in text else "ok"
    red = sorted(n for n, s in statuses.items() if s == "FAIL")
    return {"id": f"validation:{spec['id']}", "layer": "C", "status": "fail" if red else "pass",
            "reason": "exit code 1" if red else "",
            "evidence": {"runner": "pytest", "consistent": True, "tests_run": len(statuses), "failures": len(red),
                         "errors": 0, "timed_out": False, "killed": False, "output_limit_exceeded": False,
                         "truncated": False, "skipped": 0, "output_tail": "",
                         "must_pass": {n: statuses.get(n) for n in spec.get("must_pass", [])}, "failed_nodes": red}}


def router_red(nodes, workdir, sandbox_cfg, **kw):
    text = (Path(workdir) / "src" / "shop.py").read_text()
    out = {}
    for n in nodes:
        bad = "BROKE" in text
        out[n] = {"outcome": "failed" if bad else "passed", "type": "builtins.AssertionError" if bad else None,
                  "assertion": bad, "path": "tests/test_old.py" if bad else None}
    return out, None, False


def text_of(content):
    """A message's text; with prompt caching the content is a list of blocks."""
    return content if isinstance(content, str) else "".join(b.get("text", "") for b in content if isinstance(b, dict))


def conflicted_job(tmp_path, agent):
    env = Env(tmp_path, agent=agent)
    env.deps.validate, env.deps.conflict_red = router_validate, router_red
    env.code()
    env.approve()
    return env


def test_a_confirmed_report_leaves_the_job_agent_failed_and_status_says_what_the_harness_checked(tmp_path):
    env = conflicted_job(tmp_path, [BROKE_WRITE, ROUTER_REPORT])
    assert env.job().data["state"] == rj.AGENT_FAILED
    text = rj.status("jtest", jobs_dir=env.jobs)
    assert ("old tests fail with the agent's change, new tests pass (checked by the harness; which side is wrong is your "
            "call):") in text
    assert f"tests/test_old.py: {td.OLD_NODE} (builtins.AssertionError)" in text
    assert "argus abandon jtest" in text and "and a new job that names the file(s)" in text
    assert "argus retry jtest --not-a-conflict" in text
    assert "conflict (checked by the harness)" not in text
    assert "next: argus retry jtest  |" not in text                               # a bare retry is not offered


def test_a_bare_retry_after_a_confirmed_report_is_refused_with_both_choices(tmp_path):
    env = conflicted_job(tmp_path, [BROKE_WRITE, ROUTER_REPORT])
    with pytest.raises(rj.Refused) as e:
        rj.retry("jtest", cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs)
    msg = str(e.value)
    assert "BLOCKED/test_conflict" in msg and "argus abandon jtest" in msg and "--not-a-conflict" in msg
    assert env.job().data["state"] == rj.AGENT_FAILED and "a2" not in env.job().data["stages"]


def test_retry_not_a_conflict_runs_the_agent_told_so_and_it_cannot_report_again(tmp_path):
    env = conflicted_job(tmp_path, [BROKE_WRITE, ROUTER_REPORT, ROUTER_REPORT_AGAIN := call(
        "ReportConflict", {"files": ["tests/test_old.py"]}, "rc2"), ROUTER_WRITE, ROUTER_FINISH])
    rj.retry("jtest", cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs, not_a_conflict=True)
    job = env.job()
    assert job.data["state"] == rj.REVIEW_READY and job.data["stages"]["a2"]["carry"]["not_a_conflict"]["files"] == [
        "tests/test_old.py"]
    first = text_of(env.coder.calls[2]["messages"][1].content)                  # the first request of the second run
    assert "A reviewer looked at the previous run's report of a conflict and decided it is NOT one" in first
    assert f"{td.OLD_NODE} (builtins.AssertionError)" in first and "ReportConflict is not available in this run" in first
    answer = next(m.content for c in reversed(env.coder.calls) for m in c["messages"]
                  if getattr(m, "tool_call_id", None) == "rc2")
    assert answer.startswith("Refused: ReportConflict is not available in this run") and "judged the old tests right" in answer
    assert [e for e in job.data["log"] if e["what"] == "retry"][-1]["not_a_conflict"] is True


def test_the_flag_is_refused_for_a_job_whose_last_run_was_not_a_confirmed_report(tmp_path):
    env = Env(tmp_path, agent=[call("Finish", {"claims": [], "summary": "x"}, "f0"), call("Finish", {"claims": [], "summary": "x"}, "f1")])
    env.deps.validate, env.deps.conflict_red = router_validate, router_red
    env.code()
    env.approve()
    assert env.job().data["state"] == rj.AGENT_FAILED
    with pytest.raises(rj.Refused, match="only for a job whose last run ended BLOCKED/test_conflict"):
        rj.retry("jtest", cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs, not_a_conflict=True)


def test_an_unconfirmed_report_is_shown_by_status_as_not_confirmed_with_the_failed_checks(tmp_path):
    wrong = call("ReportConflict", {"files": ["tests/test_new.py"]}, "rw")
    env = conflicted_job(tmp_path, [BROKE_WRITE, wrong, call("Finish", {"claims": [], "summary": "x"}, "f0")])
    text = rj.status("jtest", jobs_dir=env.jobs)
    assert "agent reported a conflict (not confirmed): tests/test_new.py; failed checks:" in text
    assert "a red test is in a file the agent did not name" in text
    assert "argus retry jtest" in text and "--not-a-conflict" not in text         # an ordinary failed run: the ordinary retry


def test_the_report_tool_memo_key_depends_on_the_runs_conflict_state(tmp_path):
    import hashlib
    import re
    wrong = call("ReportConflict", {"files": ["tests/test_new.py"]}, "rw")
    again = call("ReportConflict", {"files": ["tests/test_new.py"]}, "rw2")
    r, model, d, red = run(tmp_path, [WRITE_NEW, wrong, again, WRITE_BOTH, FINISH])
    rows = [json.loads(k) for (k,) in sqlite3.connect(str(d / "memo.sqlite")).execute("select key from memo")]
    versions = {row[5]: row[7] for row in rows if row[0] == "tool" and re.fullmatch(r"1:[0-9a-f]{12}", str(row[7]))}
    assert set(versions) == {"rw", "rw2"}                                       # the two ReportConflict steps
    assert versions["rw"] == "1:" + hashlib.sha256(b"null").hexdigest()[:12]      # no state yet
    assert versions["rw2"] != versions["rw"]                                    # the state set after the first miss


# ---- review fixes ---------------------------------------------------------------------------------------------------------

def test_status_does_not_call_a_humans_not_a_conflict_a_report_of_the_agent(tmp_path):
    bad_finish = call("Finish", {"claims": [], "summary": "x"}, "fx")
    env = conflicted_job(tmp_path, [BROKE_WRITE, ROUTER_REPORT, bad_finish, bad_finish])
    rj.retry("jtest", cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs, not_a_conflict=True)
    text = rj.status("jtest", jobs_dir=env.jobs)
    assert env.job().data["state"] == rj.AGENT_FAILED
    assert "agent reported a conflict" not in text and "old tests fail with the agent's change" not in text
    assert "argus retry jtest" in text and "--not-a-conflict" not in text


def test_the_humans_judgement_holds_for_a_later_plain_retry_of_the_same_job(tmp_path):
    bad_finish = call("Finish", {"claims": [], "summary": "x"}, "fx")
    again = call("ReportConflict", {"files": ["tests/test_old.py"]}, "rc9")
    env = conflicted_job(tmp_path, [BROKE_WRITE, ROUTER_REPORT, bad_finish, bad_finish, again, ROUTER_WRITE, ROUTER_FINISH])
    rj.retry("jtest", cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs, not_a_conflict=True)       # a2 fails
    rj.retry("jtest", cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs)                             # a3, a plain retry
    job = env.job()
    assert job.data["stages"]["a3"]["carry"]["not_a_conflict"]["files"] == ["tests/test_old.py"]
    answer = next(m.content for c in reversed(env.coder.calls) for m in c["messages"]
                  if getattr(m, "tool_call_id", None) == "rc9")
    assert answer.startswith("Refused: ReportConflict is not available in this run") and job.data["state"] == rj.REVIEW_READY


def test_each_validation_is_checked_with_its_own_runner_timeout_and_environment(tmp_path):
    c = Case(tmp_path)
    c.contract["validation"] = [dict(c.contract["validation"][0], id="unit", environment="envA", timeout_s=11),
                                {"id": "ui", "executable": "vitest", "args": ["run", "src/a.test.js"], "timeout_s": 22,
                                 "min_tests": 1, "max_skipped": 0, "environment": "envB"}]
    ui_node = "src/a.test.js::renders"
    (c.input_dir / "src").mkdir(exist_ok=True)
    (c.input_dir / "src" / "a.test.js").write_text("//\n")
    (c.ws / "src").mkdir(exist_ok=True)
    (c.ws / "src" / "a.test.js").write_text("//\n")
    c.before = snapshot(c.input_dir)
    c.contract["scope"]["protected"] = ["tests/**", "conftest.py", "src/*.test.js"]
    c.files = ["tests/test_old.py", "src/a.test.js"]
    base = c.verdict

    def verdict():
        v = base()
        ui = {"id": "validation:ui", "layer": "C", "status": "fail", "reason": "x",
              "evidence": {"runner": "vitest", "consistent": True, "tests_run": 1, "failures": 1, "errors": 0,
                           "must_pass": {}, "failed_nodes": [ui_node]}}
        v["criteria"].insert(3, ui)
        return v
    c.verdict = verdict
    seen = []

    def red(nodes, workdir, scfg, **kw):
        seen.append((tuple(nodes), kw["runner"], kw["timeout_s"], kw["environment"], Path(workdir).name))
        failing = Path(workdir).name == "ws"
        return {n: {"outcome": "failed" if failing else "passed", "type": "Error" if failing else None,
                    "assertion": failing, "path": n.split("::")[0] if failing else None} for n in nodes}, None, False
    c.red = red
    out = c.verify()
    assert out["state"] == "confirmed", out
    assert {(s[0], s[1], s[2], s[3]) for s in seen} == {((OLD_NODE,), "pytest", 11, "envA"), ((ui_node,), "vitest", 22, "envB")}
    assert len(seen) == 6 and {n["node"] for n in out["nodes"]} == {OLD_NODE, ui_node}


def test_a_red_validation_that_is_not_in_the_contract_says_so_instead_of_failing_silently(tmp_path):
    def change(c):
        v = c.verdict()                                       # built with the contract as it is, then the contract differs
        c.verdict = lambda: v
        c.contract["validation"][0]["id"] = "other"
    out = breaks(tmp_path, change, "is not a validation of the contract")
    assert not any("TypeError" in x for x in out["unconfirmed"])


def test_a_report_beside_another_call_is_rejected_in_the_loop_and_nothing_runs(tmp_path):
    both = reply(tool_calls=[{"name": "ReportConflict", "args": {"files": ["tests/test_old.py"]}, "id": "b1"},
                             {"name": "WriteFile", "args": {"path": "src/app.py", "content": "BEHAVIOUR = 'x'\n"}, "id": "b2"}],
                 input_tokens=500, output_tokens=60)
    r, model, d, red = run(tmp_path, [both, WRITE_NEW, REPORT])
    assert "ReportConflict must be the only tool call in its reply" in tool_answer(model, "b1")
    assert (d / "workspace" / "src" / "app.py").read_text() != "BEHAVIOUR = 'x'\n" and r["blocked_reason"] == "test_conflict"


def test_red_check_ex_tells_a_missing_sandbox_from_an_unreadable_run(tmp_path, monkeypatch):
    from acceptance import validation as va
    kw = {"timeout_s": 5}

    def gone(*a, **k):
        raise va.sb.SandboxUnavailable("no docker")
    monkeypatch.setattr(va.sb, "run_command", gone)
    got, why, unavailable = va.red_check_ex([OLD_NODE], tmp_path, {}, **kw)
    assert got is None and unavailable is True and "no docker" in why
    for r in ({"timed_out": True}, {"output_limit_exceeded": True}, {"truncated": True}, {"stdout": "no record", "exit_code": 1}):
        monkeypatch.setattr(va.sb, "run_command", lambda *a, _r=r, **k: dict({"stdout": "", "exit_code": 0}, **_r))
        got, why, unavailable = va.red_check_ex([OLD_NODE], tmp_path, {}, **kw)
        assert got is None and unavailable is False and why
    assert va.red_check([OLD_NODE], tmp_path, {}, **kw) == (None, why)            # the old shape is unchanged
    nonce_run = lambda argv, **k: {"stdout": "x\n" + argv[5] + json.dumps({OLD_NODE: {"outcome": "passed"}}) + "\n", "exit_code": 0}
    monkeypatch.setattr(va.sb, "run_command", nonce_run)
    assert va.red_check_ex([OLD_NODE], tmp_path, {}, **kw) == ({OLD_NODE: {"outcome": "passed"}}, None, False)


def test_no_validation_in_the_verdict_says_so(tmp_path):
    c = Case(tmp_path)
    base = c.verdict
    c.verdict = lambda: {**base(), "criteria": [x for x in base()["criteria"] if x["layer"] != "C"]}
    out = c.verify()
    assert out["state"] == "unconfirmed" and any("the contract has no validation" in x for x in out["unconfirmed"])


def test_a_failure_in_a_file_the_input_never_had_or_with_no_file_at_all_does_not_confirm(tmp_path):
    def new_file(c):
        (c.ws / "tests" / "added_later.py").write_text("X = 1\n")        # protected by the glob, but the agent made it
        base = c.red

        def red(nodes, workdir, scfg, **kw):
            out, why, un = base(nodes, workdir, scfg, **kw)
            return {n: dict(r, path="tests/added_later.py" if r["path"] else None) for n, r in out.items()}, why, un
        c.red = red
    breaks(tmp_path / "a", new_file, "tests/added_later.py is not a file of the input")

    def no_file(c):
        base = c.red

        def red(nodes, workdir, scfg, **kw):
            out, why, un = base(nodes, workdir, scfg, **kw)
            return {n: dict(r, path=None) for n, r in out.items()}, why, un
        c.red = red
    breaks(tmp_path / "b", no_file, "no file of the repository in the failure")


def test_the_red_nodes_own_file_must_be_untouched_even_when_the_failure_points_elsewhere(tmp_path):
    def change(c):
        (c.input_dir / "tests" / "helpers.py").write_text("X = 1\n")
        (c.ws / "tests" / "helpers.py").write_text("X = 1\n")
        c.before = snapshot(c.input_dir)
        (c.ws / "tests" / "test_old.py").write_text("# touched by the agent\n")
        base = c.red

        def red(nodes, workdir, scfg, **kw):
            out, why, un = base(nodes, workdir, scfg, **kw)
            return {n: dict(r, path="tests/helpers.py" if r["path"] else None) for n, r in out.items()}, why, un
        c.red = red
    breaks(tmp_path, change, "tests/test_old.py was changed by the agent")


def test_a_workspace_run_that_cannot_be_read_does_not_confirm_and_says_so(tmp_path):
    def change(c):
        base = c.red

        def red(nodes, workdir, scfg, **kw):
            if Path(workdir).name == "ws":
                return None, "the run timed out or its output was cut", False
            return base(nodes, workdir, scfg, **kw)
        c.red = red
    breaks(tmp_path, change, "the run on the workspace could not be read")


def test_a_human_judged_run_is_not_told_that_it_already_reported(tmp_path):
    (tmp_path / "ws").mkdir()
    state = {"files": ["tests/test_old.py"], "unconfirmed": ["a human judged this is not a conflict"], "by_human": True}
    box = tl.Toolbox(str(tmp_path / "ws"), CONTRACT, {}, {"report_conflict"}, _Log(), conflict=state)
    out = box.run({"name": "ReportConflict", "args": {"files": ["tests/test_old.py"]}})
    assert out["finished"] is False and "judged the old tests right" in out["content"] and "already used" not in out["content"]


def test_the_next_prompt_explains_a_conflict_report_that_ended_an_attempt():
    from codetask.agent import _ended
    text = _ended({"end": "conflict_reported", "steps": 4, "wrote": True})
    assert "conflict_reported" not in text and "did not confirm" in text and "4 steps" in text
    assert _ended({"end": "finished", "steps": 2, "wrote": False}) == "finished after 2 steps; it changed no file"
