"""General tasks, slice 1 part B: crash-resume across processes, with the real sandbox and a file-scripted model.

Each test kills the process (os._exit) once at an exact point, resumes it, and checks the transaction boundary:
nothing committed is redone, the one uncommitted step is redone safely, every model call that was made is in the
ledger and paid for, and the run ends as an uncrashed run would. Needs Docker and a pinned image; without them the
tests are skipped with "SANDBOX NOT AVAILABLE", which scripts/verify.sh does not count as passing."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from models.fake import pos_path
from runner import load_config
from tools import sandbox as sb

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = ROOT / "fixtures" / "contracts" / "fix_divide.json"
CALC = (ROOT / "fixtures" / "repos" / "calc" / "src" / "calc.py").read_text(encoding="utf-8")
FIXED = CALC.replace("    if b == 0:\n        return 0\n", "")
CLAIMS = [{"claim": "tests_pass", "evidence": "validation:unit"},
          {"claim": "issue_fixed", "evidence": "validation:target"},
          {"claim": "file_changed", "path": "src/calc.py"}]


@pytest.fixture(scope="module")
def image():
    ok, reason = sb.status({"kind": "docker"})
    if not ok:
        pytest.skip(f"SANDBOX NOT AVAILABLE: {reason}")
    return sb.settings({})["image"]


def _reply(name, args, id):
    return {"tool_calls": [{"name": name, "args": args, "id": id}], "usage": {"input_tokens": 500, "output_tokens": 60}}


# Read, write the fix, check it, finish; one spare in case a step is legitimately bought twice.
SCRIPT = [_reply("ReadFile", {"path": "src/calc.py"}, "r1"),
          _reply("WriteFile", {"path": "src/calc.py", "content": FIXED}, "w1"),
          _reply("RunValidation", {"id": "target"}, "v1"),
          _reply("Finish", {"claims": CLAIMS, "summary": "divide raises on zero"}, "f1"),
          _reply("Finish", {"claims": CLAIMS, "summary": "divide raises on zero"}, "f2")]


def _setup(tmp_path, image, contract=CONTRACT):
    cfg = load_config()
    cfg["roles"]["coder"]["model"] = "fake:scripted"
    cfg["sandbox"] = {"kind": "docker", "image": image}
    (tmp_path / "config.yaml").write_text(yaml.safe_dump(cfg))
    (tmp_path / "script.json").write_text(json.dumps(SCRIPT))
    c = tmp_path / "contract.json"
    c.write_text(Path(contract).read_text(encoding="utf-8"), encoding="utf-8")
    return c


def _cli(tmp_path, *extra):
    env = {**os.environ, "ARGUS_FAKE_SCRIPT": str(tmp_path / "script.json")}
    env.pop("ARGUS_LIVE", None)
    base = [sys.executable, "scripts/run_code_task.py", "--config", str(tmp_path / "config.yaml"),
            "--contract", str(tmp_path / "contract.json"), "--run-id", "rc", "--runs-dir", str(tmp_path / "runs"),
            "--quiet"]
    return subprocess.run(base + list(extra), cwd=ROOT, capture_output=True, text=True, env=env, timeout=300)


def _events(tmp_path):
    return [json.loads(l) for l in (tmp_path / "runs" / "rc" / "events.jsonl").read_text().splitlines() if l.strip()]


def _model_calls(tmp_path):
    p = Path(pos_path(str(tmp_path / "script.json"), "default"))
    return int(p.read_text()) if p.exists() else 0


def _crash_and_resume(tmp_path, image, point, between=None):
    _setup(tmp_path, image)
    r1 = _cli(tmp_path, "--crash-at", point)
    assert r1.returncode == 42, (r1.stdout[-2000:], r1.stderr[-2000:])
    if between:
        between()
    r2 = _cli(tmp_path, "--resume")
    result = json.loads((tmp_path / "runs" / "rc" / "result.json").read_text())
    return r2, result, _events(tmp_path)


def _split(evs):
    i = next(n for n, e in enumerate(evs) if e["event"] == "crash_simulated")
    return evs[:i], evs[i:]


def _assert_nothing_committed_is_redone(evs):
    before, after = _split(evs)
    llm = {(e["iteration"], e["step"]) for e in before if e["event"] == "step_committed" and e["kind"] == "llm"}
    called = {(e["iteration"], e["step"]) for e in after if e["event"] == "llm_call" and e.get("node") == "agent"}
    assert not llm & called, llm & called
    tools = {(e["iteration"], e["step"], e["tool"]) for e in before
             if e["event"] == "step_committed" and e["kind"] == "tool"}
    rerun = {(e["iteration"], e["step"], e["tool"]) for e in after
             if e["event"] == "step_committed" and e["kind"] == "tool"}
    assert not tools & rerun, tools & rerun
    nodes = {e["node"] for e in before if e["event"] == "result_committed"}
    redone = {e["node"] for e in after if e["event"] == "node_start"}
    assert not nodes & redone, nodes & redone


def _assert_done(tmp_path, r2, result):
    assert r2.returncode == 0, (r2.stdout[-2000:], r2.stderr[-2000:])
    assert result["status"] == "DONE", result
    ws = tmp_path / "runs" / "rc" / "workspace"
    assert (ws / "src" / "calc.py").read_text() == FIXED and (ws / "SUMMARY.json").exists()


POINTS = ["setup@after_copy", "agent@llm_committed", "agent@after_tool", "agent@tool_committed",
          "agent@after_commit", "acceptance@after_verdict", "acceptance@after_commit"]


@pytest.mark.parametrize("point", POINTS)
def test_a_crash_at_a_transaction_boundary_redoes_only_uncommitted_work(tmp_path, image, point):
    r2, result, evs = _crash_and_resume(tmp_path, image, point)
    _assert_done(tmp_path, r2, result)
    _assert_nothing_committed_is_redone(evs)
    assert _model_calls(tmp_path) == 4                       # exactly as many model calls as without a crash
    assert result["llm_calls"] == 4 and result["llm_calls_unknown"] == 0
    verdicts = [e for e in evs if e["event"] == "acceptance_verdict"]
    if point == "acceptance@after_commit":
        assert len(verdicts) == 1                            # a committed verdict is never recomputed
    if point == "acceptance@after_verdict":
        assert len(verdicts) == 2 and verdicts[0]["workspace_digest"] == verdicts[1]["workspace_digest"]


def test_a_crash_before_a_reply_is_committed_buys_it_again_and_pays_for_both(tmp_path, image):
    r2, result, evs = _crash_and_resume(tmp_path, image, "agent@after_llm")
    _assert_done(tmp_path, r2, result)
    before, after = _split(evs)
    assert [e["step"] for e in before if e["event"] == "llm_call"] == [0]   # step 0 was bought ...
    assert any(e["event"] == "llm_call" and e["step"] == 0 for e in after)  # ... and bought again
    assert result["llm_calls"] == _model_calls(tmp_path) == 4               # every call is in the ledger
    restored = [e for e in after if e["event"] == "reservation_restored"]
    assert restored and restored[0]["calls"] == 1                           # the lost call stays charged


def test_a_write_that_ran_but_was_not_committed_runs_again_with_the_same_result(tmp_path, image):
    # The write (step 1) changed the file, then the process died before its result was committed. Resume replays
    # the committed reply and runs the write again. Its effect must be idempotent: the file ends up exactly as after
    # one write (a write that appended when repeated is caught here), and no model call is bought again.
    r2, result, evs = _crash_and_resume(tmp_path, image, "agent@after_tool:WriteFile")
    _assert_done(tmp_path, r2, result)
    ran = [e for e in evs if e["event"] == "tool_call" and e.get("tool") == "write_file"]
    committed = [e for e in evs if e["event"] == "step_committed" and e.get("tool") == "WriteFile"]
    assert len(ran) == 2 and len(committed) == 1
    assert _model_calls(tmp_path) == 4 and result["llm_calls"] == 4


def test_resume_uses_the_frozen_contract_not_the_edited_file(tmp_path, image):
    def edit():
        (tmp_path / "contract.json").write_text("{this is no longer a contract")
    r2, result, evs = _crash_and_resume(tmp_path, image, "agent@tool_committed", between=edit)
    _assert_done(tmp_path, r2, result)
    frozen_sha = next(e["sha256"] for e in evs if e["event"] == "contract_frozen")
    assert result["contract_sha"] == frozen_sha


def test_a_frozen_contract_changed_while_crashed_blocks_the_run(tmp_path, image):
    def tamper():
        p = tmp_path / "runs" / "rc" / "contract.json"
        p.write_text(p.read_text().replace('"min_tests":7', '"min_tests":1'))
    r2, result, evs = _crash_and_resume(tmp_path, image, "agent@tool_committed", between=tamper)
    assert result["status"] == "BLOCKED" and result["blocked_reason"] == "contract_changed"


def test_resume_removes_containers_the_crashed_run_left_running(tmp_path, image):
    started = []

    def orphan():   # what a crash mid-validation leaves: a container of this run that nobody will time out
        cid = subprocess.run(["docker", "run", "-d", "--rm", "--network", "none", "--label", "argus.sandbox=1",
                              "--label", "argus.run=rc", image, "python3", "-c", "import time; time.sleep(300)"],
                             capture_output=True, text=True, check=True).stdout.strip()
        started.append(cid)
    r2, result, evs = _crash_and_resume(tmp_path, image, "agent@tool_committed", between=orphan)
    _assert_done(tmp_path, r2, result)
    alive = subprocess.run(["docker", "ps", "-q", "--no-trunc", "--filter", f"id={started[0]}"],
                           capture_output=True, text=True).stdout.split()
    assert alive == []
    assert next(e for e in evs if e["event"] == "leftover_containers_removed")["count"] == 1


def test_a_real_model_is_refused_without_the_live_switch(tmp_path, image):
    _setup(tmp_path, image)
    cfg = yaml.safe_load((tmp_path / "config.yaml").read_text())
    cfg["roles"]["coder"]["model"] = "anthropic:claude-sonnet-5-5"
    (tmp_path / "config.yaml").write_text(yaml.safe_dump(cfg))
    r = _cli(tmp_path)
    assert r.returncode == 2 and "ARGUS_LIVE=1" in r.stderr and not (tmp_path / "runs" / "rc").exists()
