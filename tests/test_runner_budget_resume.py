"""FAILED_BUDGET in the CSV runner is durable: it is written to the LangGraph checkpoint, not only to result.json, so a
new process resuming the run finds it finished and does nothing (no model call, no node, no spend).

Found in the PR #22 review for code tasks (codetask/run.py); the CSV runner had the same pattern: guard raises
BudgetExceeded / EstimateExceeded before the node's result is committed, so the checkpoint still had that node pending.
"""
import copy
import json
import os
import subprocess
import sys

import yaml

from runner import ROOT, load_config

# Only what a resume of a finished run may add to the event log.
ALLOWED_AFTER_RESUME = {"resume", "run_end"}


def _events(run_dir):
    return [json.loads(l) for l in (run_dir / "events.jsonl").read_text().splitlines() if l.strip()]


def _cli(tmp_path, cfg, *extra):
    (tmp_path / "config.yaml").write_text(yaml.safe_dump(cfg))
    env = {**os.environ, "ARGUS_FAKE_SCRIPT": str(tmp_path / "script.json")}
    base = [sys.executable, "main.py", "--config", str(tmp_path / "config.yaml"), "--scenario", "pass",
            "--run-id", "rb", "--runs-dir", str(tmp_path / "runs"), "--quiet"]
    return subprocess.run(base + list(extra), cwd=ROOT, capture_output=True, text=True, env=env, timeout=300)


def _model_calls(tmp_path):
    total = 0
    for p in tmp_path.glob("script.json.pos*"):
        if not p.name.endswith(".tmp"):
            total += int(p.read_text())
    return total


def _run_then_resume(tmp_path, cfg):
    r1 = _cli(tmp_path, cfg)
    run_dir = tmp_path / "runs" / "rb"
    assert (run_dir / "result.json").exists(), (r1.stdout[-1500:], r1.stderr[-1500:])
    first = json.loads((run_dir / "result.json").read_text())
    n, calls = len(_events(run_dir)), _model_calls(tmp_path)
    r2 = _cli(tmp_path, cfg, "--resume")
    assert r2.returncode == r1.returncode, (r2.stdout[-1500:], r2.stderr[-1500:])
    second = json.loads((run_dir / "result.json").read_text())
    return first, second, _events(run_dir)[n:], calls


def _assert_resume_did_nothing(tmp_path, first, second, after, calls):
    assert second["status"] == first["status"] == "FAILED_BUDGET", (first, second)
    assert second["stop_reason"] == first["stop_reason"]
    assert _model_calls(tmp_path) == calls
    assert second["usd_billed"] == first["usd_billed"] and second["llm_calls"] == first["llm_calls"]
    assert {e["event"] for e in after} <= ALLOWED_AFTER_RESUME, [e["event"] for e in after]


def test_a_worker_overspend_is_a_durable_failed_budget(tmp_path):
    cfg = copy.deepcopy(load_config())
    cfg["impl"]["worker"] = "llm"
    cfg.pop("llm_token_estimates", None)
    cfg["roles"]["worker"]["model"] = "fake:scripted"
    cfg["token_estimates"]["worker"] = 20_000
    cfg["llm"]["base_delay"] = 0
    # Every worker's first reply is billed 30,000 input tokens against a 20,000-token reservation.
    over = {"tool_calls": [{"name": "ReadData", "args": {}, "id": "r1"}],
            "usage": {"input_tokens": 30_000, "output_tokens": 50}}
    (tmp_path / "script.json").write_text(json.dumps({t: [over] * 3 for t in ("T1", "T2", "T3")}))
    first, second, after, calls = _run_then_resume(tmp_path, cfg)
    assert first["stop_reason"].startswith("budget_violation") and calls >= 1 and first["usd_billed"] > 0
    _assert_resume_did_nothing(tmp_path, first, second, after, calls)


def test_a_refused_iteration_is_a_durable_failed_budget(tmp_path):
    cfg = copy.deepcopy(load_config())
    cfg["budget"]["max_tokens"] = 100          # not even the first iteration's reservation fits
    (tmp_path / "script.json").write_text("[]")
    first, second, after, calls = _run_then_resume(tmp_path, cfg)
    assert first["stop_reason"] == "max_tokens"
    _assert_resume_did_nothing(tmp_path, first, second, after, calls)
