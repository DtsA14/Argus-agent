"""General tasks, slice 1 part B, in one process with scripted models and an injected validation (no Docker):
the status machine, the agent's tools and scope, the frozen contract, and budget admission from the ledger.
Crash-resume across processes, with the real sandbox, is in tests/test_codetask_crash.py."""
import copy
import json
import sys
from pathlib import Path

import pytest

from codetask import status as st
from codetask.run import admission, run_code_task, settings
from harness.events import EventLog
from models.fake import CallableChatModel, FakeHTTPError, StrictScriptedChatModel, reply
from runner import load_config

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="the path jail needs openat; the VM runs these")

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = json.loads((ROOT / "fixtures" / "contracts" / "fix_divide.json").read_text(encoding="utf-8"))
CALC = (ROOT / "fixtures" / "repos" / "calc" / "src" / "calc.py").read_text(encoding="utf-8")
TEST = (ROOT / "fixtures" / "repos" / "calc" / "tests" / "test_calc.py").read_text(encoding="utf-8")
FIXED = CALC.replace("    if b == 0:\n        return 0\n", "")
TARGET = "tests.test_calc.CalcTest.test_divide_by_zero"
CLAIMS = [{"claim": "tests_pass", "evidence": "validation:unit"},
          {"claim": "issue_fixed", "evidence": "validation:target"},
          {"claim": "file_changed", "path": "src/calc.py"}]


def cfg(**budget):
    c = load_config()
    c["roles"]["coder"]["model"] = "fake:scripted"
    c["budget"].update(budget)
    return c


def call(name, args, id):
    return reply(tool_calls=[{"name": name, "args": args, "id": id}], input_tokens=500, output_tokens=60)


READ = call("ReadFile", {"path": "src/calc.py"}, "r1")
WRITE = call("WriteFile", {"path": "src/calc.py", "content": FIXED}, "w1")
CHECK = call("RunValidation", {"id": "target"}, "v1")
FINISH = call("Finish", {"claims": CLAIMS, "summary": "divide raises on zero"}, "f1")


def fake_validate(spec, workspace, sandbox_cfg, log=None):
    """Stands in for the sandbox: passes only when the bug is really fixed and the tests are the original ones."""
    ws = Path(workspace)
    ok = (ws / "src" / "calc.py").read_text() == FIXED and (ws / "tests" / "test_calc.py").read_text() == TEST
    must = {t: "ok" if ok else "FAIL" for t in spec.get("must_pass", [])}
    return {"id": f"validation:{spec['id']}", "layer": "C", "status": "pass" if ok else "fail",
            "reason": "" if ok else "exit code 1; unittest outcome FAILED",
            "evidence": {"must_pass": must, "tests_run": 7, "failures": 0 if ok else 1, "output_tail": ""}}


def run(tmp_path, script, *, contract=None, config=None, validate=fake_validate, preflight=lambda: (True, "ok"),
        model=None, run_id="t", resume=False):
    path = tmp_path / "contract.json"
    if not path.exists():
        path.write_text(json.dumps(contract or CONTRACT), encoding="utf-8")
    # Strict: like DeepSeek, it refuses a request in which any tool call id is left unanswered.
    model = model or StrictScriptedChatModel(script=list(script))
    r = run_code_task(contract_path=path, run_id=run_id, runs_dir=tmp_path / "runs", cfg=config or cfg(),
                      models={"coder": model}, validate=validate, preflight=preflight, resume=resume)
    return r, model, tmp_path / "runs" / run_id


def events(run_dir):
    return [json.loads(l) for l in (run_dir / "events.jsonl").read_text().splitlines()]


def statuses_seen(run_dir):
    return [(e["old"], e["new"]) for e in events(run_dir) if e["event"] == "status"]


# ---- the status machine ---------------------------------------------------------------------------

def test_only_legal_transitions_are_allowed():
    assert st.transition(None, st.RUNNING) == st.RUNNING
    assert st.transition(st.RUNNING, st.BLOCKED, "sandbox_unavailable") == st.BLOCKED
    for terminal in st.TERMINAL:
        for new in st.STATUSES:
            with pytest.raises(st.IllegalTransition):
                st.transition(terminal, new, "invalid_contract" if new == st.BLOCKED else None)
    with pytest.raises(st.IllegalTransition):
        st.transition(st.RUNNING, st.BLOCKED)                       # BLOCKED must say why
    with pytest.raises(st.IllegalTransition):
        st.transition(st.RUNNING, st.BLOCKED, "it felt wrong")      # and only a known why
    with pytest.raises(st.IllegalTransition):
        st.transition(st.RUNNING, st.DONE, "sandbox_unavailable")   # only BLOCKED carries a reason
    with pytest.raises(st.IllegalTransition):
        st.transition(None, st.DONE)                                # nothing is done before it ran


# ---- outcomes ---------------------------------------------------------------------------------------

def test_a_real_fix_with_honest_claims_is_done(tmp_path):
    r, model, d = run(tmp_path, [READ, WRITE, CHECK, FINISH])
    assert r["status"] == st.DONE and r["attempts"] == 1 and len(model.calls) == 4
    assert (d / "workspace" / "src" / "calc.py").read_text() == FIXED
    assert json.loads((d / "workspace" / "SUMMARY.json").read_text())["claims"][0]["claim"] == "tests_pass"
    assert json.loads((d / "verdict_0.json").read_text())["outcome"] == "pass"
    assert statuses_seen(d) == [(None, "RUNNING"), ("RUNNING", "DONE")]
    assert r["usd_billed"] > 0 and r["llm_calls"] == 4
    assert (ROOT / "fixtures" / "repos" / "calc" / "src" / "calc.py").read_text() == CALC   # input untouched


def test_claiming_success_without_doing_the_work_fails_and_stops_when_stagnant(tmp_path):
    lazy = call("Finish", {"claims": CLAIMS, "summary": "fixed"}, "f1")
    r, model, d = run(tmp_path, [lazy, lazy])
    assert r["status"] == st.FAILED_ACCEPTANCE and r["stop_reason"].startswith("stagnant") and r["attempts"] == 2
    second = model.calls[1]["messages"][1].content
    assert "did not meet the contract" in second and "validation:target" in second   # the feedback reached it
    assert statuses_seen(d) == [(None, "RUNNING"), ("RUNNING", "RUNNING"), ("RUNNING", "FAILED_ACCEPTANCE")]


def test_feedback_leads_to_a_fix_in_the_next_attempt(tmp_path):
    lazy = call("Finish", {"claims": CLAIMS, "summary": "fixed"}, "f0")
    r, model, d = run(tmp_path, [lazy, WRITE, FINISH])
    assert r["status"] == st.DONE and r["attempts"] == 2


def test_no_attempt_beyond_max_iterations(tmp_path):
    c = copy.deepcopy(CONTRACT)
    c["limits"]["max_iterations"] = 1
    r, model, d = run(tmp_path, [call("Finish", {"claims": CLAIMS, "summary": "x"}, "f1")], contract=c)
    assert r["status"] == st.FAILED_ACCEPTANCE and r["stop_reason"] == "max_iterations" and len(model.calls) == 1


# ---- scope and the tools ------------------------------------------------------------------------------

@pytest.mark.parametrize("path,word", [("tests/test_calc.py", "protected"), ("setup.py", "outside the writable"),
                                        ("SUMMARY.json", "written by Finish"), ("../evil.py", "Refused"),
                                        ("/tmp/evil.py", "Refused"), ("src/../../evil.py", "Refused")])
def test_writes_outside_the_scope_are_refused_and_change_nothing(tmp_path, path, word):
    bad = call("WriteFile", {"path": path, "content": "x = 1\n"}, "b1")
    r, model, d = run(tmp_path, [bad, WRITE, FINISH])
    answer = next(m for m in model.calls[1]["messages"] if getattr(m, "tool_call_id", None) == "b1").content
    assert word in answer
    assert r["status"] == st.DONE                                          # the refused write changed nothing
    assert (d / "workspace" / "tests" / "test_calc.py").read_text() == TEST
    assert not (tmp_path / "runs" / "evil.py").exists() and not (tmp_path / "evil.py").exists()
    assert not Path("/tmp/evil.py").exists() or Path("/tmp/evil.py").read_text() != "x = 1\n"


def test_a_denied_tool_is_never_run(tmp_path):
    c = cfg()
    c["tools"]["coder"] = ["list_files", "read_file", "run_validation"]       # no write_file
    r, model, d = run(tmp_path, [WRITE, FINISH], config=c)
    answer = next(m for m in model.calls[1]["messages"] if getattr(m, "tool_call_id", None) == "w1").content
    assert answer.startswith("Denied") and (d / "workspace" / "src" / "calc.py").read_text() == CALC


def test_finish_must_be_alone_and_well_formed(tmp_path):
    mixed = reply(tool_calls=[{"name": "WriteFile", "args": {"path": "src/calc.py", "content": FIXED}, "id": "w0"},
                              {"name": "Finish", "args": {"claims": CLAIMS, "summary": "x"}, "id": "f0"}])
    bad = call("Finish", {"claims": [{"claim": "everything_works"}], "summary": "x"}, "f9")
    r, model, d = run(tmp_path, [mixed, bad, WRITE, FINISH])
    assert r["status"] == st.DONE
    assert any(e["event"] == "finish_rejected" for e in events(d))
    third = model.calls[2]["messages"]
    assert "unknown claim kind" in next(m for m in third if getattr(m, "tool_call_id", None) == "f9").content


# ---- blocked ----------------------------------------------------------------------------------------------

def test_an_invalid_contract_blocks_before_anything_is_spent(tmp_path):
    c = copy.deepcopy(CONTRACT)
    c["validation"][0]["executable"] = "sh"
    r, model, d = run(tmp_path, [], contract=c)
    assert r["status"] == st.BLOCKED and r["blocked_reason"] == "invalid_contract"
    assert r["llm_calls"] == 0 and not (d / "workspace").exists()


def test_no_sandbox_blocks_before_anything_is_spent(tmp_path):
    r, model, d = run(tmp_path, [], preflight=lambda: (False, "docker not found"))
    assert r["status"] == st.BLOCKED and r["blocked_reason"] == "sandbox_unavailable" and r["llm_calls"] == 0


def test_a_sandbox_lost_during_the_run_blocks_and_is_not_a_pass(tmp_path):
    def gone(spec, workspace, sandbox_cfg, log=None):
        return {"id": f"validation:{spec['id']}", "layer": "C", "status": "blocked",
                "reason": "sandbox unavailable: daemon down", "evidence": {}}
    r, model, d = run(tmp_path, [WRITE, FINISH], validate=gone)
    assert r["status"] == st.BLOCKED and r["blocked_reason"] == "sandbox_unavailable"


def test_a_provider_failure_blocks_after_the_workspace_is_checked(tmp_path):
    r, model, d = run(tmp_path, [FakeHTTPError(401, "invalid api key")])
    assert r["status"] == st.BLOCKED and r["blocked_reason"] == "provider_failed"
    assert (d / "verdict_0.json").exists()                     # the harness still checked what was there


def test_a_contract_changed_after_setup_blocks_the_run(tmp_path):
    def respond(messages):
        frozen = tmp_path / "runs" / "t" / "contract.json"
        frozen.write_text(frozen.read_text().replace('"max_iterations":3', '"max_iterations":9'))
        return FINISH
    r, model, d = run(tmp_path, [], model=CallableChatModel(respond=respond))
    assert r["status"] == st.BLOCKED and r["blocked_reason"] == "contract_changed"


def test_the_repository_contract_is_never_read_after_setup(tmp_path):
    def respond(messages):
        (tmp_path / "contract.json").write_text("{not json")              # the human's file, edited mid-run
        return FINISH if len(model.calls) > 1 else WRITE
    model = CallableChatModel(respond=respond)
    r, model, d = run(tmp_path, [], model=model)
    assert r["status"] == st.DONE


# ---- budget ------------------------------------------------------------------------------------------------

def test_no_attempt_starts_when_one_attempt_does_not_fit(tmp_path):
    c = cfg(max_usd=0.01)                                  # one attempt reserves 30,000 x $5/M = $0.15
    r, model, d = run(tmp_path, [WRITE, FINISH], config=c)
    assert r["status"] == st.FAILED_BUDGET and r["llm_calls"] == 0 and len(model.calls) == 0


def test_another_attempt_starts_only_if_its_whole_reservation_fits(tmp_path):
    # One attempt reserves $0.15. After attempt 0 the ledger shows $0.0008 spent, and $0.0008 + $0.15 > $0.1505.
    c = cfg(max_usd=0.1505)
    lazy = call("Finish", {"claims": CLAIMS, "summary": "x"}, "f1")
    r, model, d = run(tmp_path, [lazy, WRITE, FINISH], config=c)
    assert r["status"] == st.FAILED_ACCEPTANCE and r["stop_reason"] == "max_usd" and len(model.calls) == 1
    assert r["usd_billed"] <= 0.1505


def test_admission_counts_calls_cut_off_by_a_crash_at_their_worst_case(tmp_path):
    log = EventLog(tmp_path / "e.jsonl")
    lim = settings(cfg(max_usd=0.20), CONTRACT)
    assert admission(log, lim) is None
    log.emit("llm_call_started", call_id="x", node="agent", task="fix_divide", iteration=0, step=0,
             worst_tokens=2000, worst_usd_nano=60_000_000)    # $0.06 cut off by a crash: never answered
    assert admission(log, lim) == "max_usd"                  # $0.06 + $0.15 > $0.20


def test_a_finished_run_is_not_continued_by_resume(tmp_path):
    r1, model, d = run(tmp_path, [WRITE, FINISH])
    r2, model2, _ = run(tmp_path, [], resume=True)
    assert r2["status"] == r1["status"] == st.DONE and len(model2.calls) == 0
    assert r2["usd_billed"] == r1["usd_billed"]


# ---- claims_v2: an agent that cannot finish may claim nothing -------------------------------------------------

def v2_contract(**limits):
    c = copy.deepcopy(CONTRACT)
    c["artifacts"][0]["schema"] = "claims_v2"
    c["limits"].update(limits)
    return c


def test_with_claims_v2_an_empty_finish_ends_the_attempt_and_the_task_still_fails(tmp_path):
    nothing = call("Finish", {"claims": [], "summary": "I could not fix it."}, "f1")
    r, model, d = run(tmp_path, [nothing, nothing], contract=v2_contract())
    assert r["status"] == st.FAILED_ACCEPTANCE and r["attempts"] == 2              # honest, but not done
    assert json.loads((d / "workspace" / "SUMMARY.json").read_text())["claims"] == []
    assert not any(e["event"] == "finish_rejected" for e in events(d))
    answers = [m.content for c in model.calls for m in c["messages"] if getattr(m, "tool_call_id", None) == "f1"]
    assert not any(a.startswith("Rejected") for a in answers)


def test_with_claims_v1_an_empty_finish_is_still_rejected(tmp_path):
    nothing = call("Finish", {"claims": [], "summary": "I could not fix it."}, "f0")
    v1 = copy.deepcopy(CONTRACT)
    v1["artifacts"][0]["schema"] = "claims_v1"
    r, model, d = run(tmp_path, [nothing, WRITE, FINISH], contract=v1)
    answer = next(m for m in model.calls[1]["messages"] if getattr(m, "tool_call_id", None) == "f0").content
    assert "claims must be a list of 1 to 50 claims" in answer and r["status"] == st.DONE


def test_with_claims_v2_a_real_fix_needs_no_claims_to_be_done(tmp_path):
    r, model, d = run(tmp_path, [WRITE, call("Finish", {"claims": [], "summary": "fixed"}, "f1")],
                      contract=v2_contract())
    assert r["status"] == st.DONE


# ---- contract tools: search_files only where the frozen contract adds it -----------------------------------------

def bound(model):
    return [t.__name__ for t in model.bound_tools]


def test_a_contract_without_tools_runs_exactly_as_before(tmp_path):
    r, model, d = run(tmp_path, [WRITE, FINISH])
    assert r["status"] == st.DONE and "SearchFiles" not in bound(model)
    assert "SearchFiles" not in model.calls[0]["messages"][0].content      # the prompt does not mention it
    assert r["tools"] == load_config()["tools"]["coder"]
    (e,) = [e for e in events(d) if e["event"] == "tools_effective"]
    assert e["from_contract"] == [] and e["tools"] == r["tools"]


def test_a_contract_can_add_search_files_for_its_own_run(tmp_path):
    c = copy.deepcopy(CONTRACT)
    c["tools"] = ["search_files"]
    find = call("SearchFiles", {"text": "return 0"}, "s1")
    r, model, d = run(tmp_path, [find, WRITE, FINISH], contract=c)
    assert r["status"] == st.DONE and "SearchFiles" in bound(model) and "search_files" in r["tools"]
    answer = next(m for m in model.calls[1]["messages"] if getattr(m, "tool_call_id", None) == "s1").content
    assert answer.startswith("src/calc.py:") and "return 0" in answer
    assert next(e for e in events(d) if e["event"] == "tools_effective")["from_contract"] == ["search_files"]


def test_a_contract_granting_another_tool_is_blocked_before_any_model_call(tmp_path):
    c = copy.deepcopy(CONTRACT)
    c["tools"] = ["run_shell"]
    r, model, d = run(tmp_path, [FINISH], contract=c)
    assert r["status"] == st.BLOCKED and r["blocked_reason"] == "invalid_contract" and len(model.calls) == 0
