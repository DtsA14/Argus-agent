"""Two gaps found by the 3a v2 live runs (pilots/m6_pilot3/3a/live/pilot3a4/RESULT.md, section 5):

1. scripts/audit_run.py rebuilt every step from the memo but did not insert D3's auto-validation message, so a run with
   auto-validation showed a prompt-hash mismatch (pilot3a4: 8 of 9 checked, 1 mismatch at s7) although the run was right.
2. A failure of the provider's token count (before llm_call_started) killed the process (pilot3a3: a key pasted twice),
   leaving no final status. It must end like any provider failure: the attempt llm_failed, the run BLOCKED provider_failed.

fixtures/audit/pilot3a4/ is the recorded live run (contract, events, memo, result; no key in any of them).
"""
import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import harness.llm as llm
from codetask import status as st
from codetask.run import run_code_task
from models.fake import FakeHTTPError, StrictScriptedChatModel, reply
from runner import load_config

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = json.loads((ROOT / "fixtures" / "contracts" / "fix_divide.json").read_text(encoding="utf-8"))
CALC = (ROOT / "fixtures" / "repos" / "calc" / "src" / "calc.py").read_text(encoding="utf-8")
TEST = (ROOT / "fixtures" / "repos" / "calc" / "tests" / "test_calc.py").read_text(encoding="utf-8")
FIXED = CALC.replace("    if b == 0:\n        return 0\n", "")
CLAIMS = [{"claim": "tests_pass", "evidence": "validation:unit"},
          {"claim": "issue_fixed", "evidence": "validation:target"},
          {"claim": "file_changed", "path": "src/calc.py"}]
on_vm = pytest.mark.skipif(sys.platform == "win32", reason="the path jail needs openat; the VM runs these")


def call(name, args, id):
    return reply(tool_calls=[{"name": name, "args": args, "id": id}], input_tokens=500, output_tokens=60)


WRITE_BAD = call("WriteFile", {"path": "src/calc.py", "content": CALC + "\noops\n"}, "b1")
WRITE = call("WriteFile", {"path": "src/calc.py", "content": FIXED}, "w1")
FINISH = call("Finish", {"claims": CLAIMS, "summary": "divide raises on zero"}, "f1")


def validate(spec, workspace, sandbox_cfg, log=None):
    ws = Path(workspace)
    ok = (ws / "src" / "calc.py").read_text() == FIXED and (ws / "tests" / "test_calc.py").read_text() == TEST
    return {"id": f"validation:{spec['id']}", "layer": "C", "status": "pass" if ok else "fail",
            "reason": "" if ok else "exit code 1",
            "evidence": {"must_pass": {t: "ok" if ok else "FAIL" for t in spec.get("must_pass", [])},
                         "tests_run": 7, "failures": 0 if ok else 1, "output_tail": "" if ok else
                         "tests/test_calc.py:21: in test_x\nE   NameError: name 'oops' is not defined\n"}}


def cfg(**code_task):
    c = load_config()
    c["roles"]["coder"]["model"] = "fake:scripted"
    c["llm"]["base_delay"] = 0
    c["code_task"].update(code_task)
    return c


def run(tmp_path, script, config=None, contract=CONTRACT):
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(contract), encoding="utf-8")
    r = run_code_task(contract_path=path, run_id="t", runs_dir=tmp_path / "runs", cfg=config or cfg(),
                      models={"coder": StrictScriptedChatModel(script=list(script))}, validate=validate,
                      preflight=lambda: (True, "ok"))
    return r, tmp_path / "runs" / "t"


def events(d, kind=None):
    evs = [json.loads(l) for l in (d / "events.jsonl").read_text().splitlines() if l.strip()]
    return [e for e in evs if kind is None or e["event"] == kind]


def audit(run_dir):
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "audit_run.py"), str(run_dir)], capture_output=True,
                         text=True, cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT)}, timeout=120)
    assert out.returncode == 0, out.stderr[-800:]
    return out.stdout


# ---- 1. the audit knows D3's message ---------------------------------------------------------------------------

def test_the_audit_reproduces_every_prompt_of_the_recorded_live_run_pilot3a4():
    out = audit(ROOT / "fixtures" / "audit" / "pilot3a4")
    assert "prompt_hash checked 9, mismatches 0" in out, out[-1500:]          # before the fix: checked 8, mismatches 1


@on_vm
def test_the_audit_reproduces_every_prompt_of_a_run_with_auto_validation(tmp_path):
    r, d = run(tmp_path, [WRITE_BAD, WRITE, FINISH], config=cfg(auto_validate=True, auto_validate_max=4))
    assert r["status"] == st.DONE
    assert sum(e["validated"] for e in events(d, "after_step")) == 2           # two messages to insert
    assert "prompt_hash checked 3, mismatches 0" in audit(d)


# ---- 2. a failed token count ends the run with a status ---------------------------------------------------------

def counter_that(fails):
    """A provider counter that raises fails[i] on call i (None: answers 500 tokens)."""
    seen = []

    def count(messages, tools):
        seen.append(1)
        exc = fails[len(seen) - 1] if len(seen) <= len(fails) else None
        if exc is not None:
            raise exc
        return 500
    return count, seen


@on_vm
def test_a_count_refused_by_the_provider_blocks_the_run_and_sends_nothing(tmp_path, monkeypatch):
    count, seen = counter_that([FakeHTTPError(401, "invalid x-api-key")])
    monkeypatch.setattr(llm, "provider_counter", lambda model, margin: (count, True))
    r, d = run(tmp_path, [WRITE, FINISH])                                     # returns: the process did not die
    assert r["status"] == st.BLOCKED and r["blocked_reason"] == "provider_failed"
    assert json.loads((d / "result.json").read_text())["status"] == st.BLOCKED
    assert not events(d, "llm_call_started") and r["llm_calls"] == 0 and r["usd_billed"] == 0
    failed = events(d, "llm_count_failed")
    assert [(f["attempt"], f["transient"], f["http_status"]) for f in failed] == [(1, False, 401)]
    assert "invalid x-api-key" in failed[0]["error"] and len(seen) == 1     # not retried
    assert [e["reason"] for e in events(d, "attempt_end")] == ["llm_failed"]


@on_vm
def test_a_transient_count_failure_is_retried_and_the_run_goes_on(tmp_path, monkeypatch):
    count, seen = counter_that([FakeHTTPError(529, "overloaded"), FakeHTTPError(503)])
    monkeypatch.setattr(llm, "provider_counter", lambda model, margin: (count, True))
    r, d = run(tmp_path, [WRITE, FINISH])
    assert r["status"] == st.DONE
    assert [(f["attempt"], f["transient"]) for f in events(d, "llm_count_failed")] == [(1, True), (2, True)]
    assert len(events(d, "llm_call_started")) == 2                           # each model call sent once


@on_vm
def test_a_count_that_keeps_failing_stops_after_the_allowed_attempts(tmp_path, monkeypatch):
    count, seen = counter_that([FakeHTTPError(503)] * 10)
    monkeypatch.setattr(llm, "provider_counter", lambda model, margin: (count, True))
    r, d = run(tmp_path, [WRITE, FINISH])
    attempts = load_config()["llm"]["attempts"]
    assert r["status"] == st.BLOCKED and r["blocked_reason"] == "provider_failed"
    assert len(seen) == attempts and len(events(d, "llm_count_failed")) == attempts
    assert not events(d, "llm_call_started")
