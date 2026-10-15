"""Phase 2e/3e: scripts/smoke_live.py, the one live run (3e: writer and judge live too). Tested with scripted fake models only: no network, no cost.

What must hold before real money is spent: nothing happens without ARGUS_LIVE=1, the USD cap can only be
lowered, unpriced models and missing keys are refused before anything is created, workers run one at a
time, and a failed run is never retried."""
import copy
import json
import math
import os
import subprocess
import sys
import threading
import time

import pytest
import yaml

import dataset
import graph as graph_module
from nodes.contract import SALES_REPORT
from nodes.synthesize import template_recommendations
from runner import ROOT, load_config, run_task
from scripts import smoke_live
from scripts.smoke_live import SmokeRefused, prepare_config

TRUTH = dataset.truth()
VALUES = {
    "T1": {"rows": 24, "months": [m for m, _ in TRUTH["trend"]], "products": ["Kopi", "Roti", "Susu", "Teh"]},
    "T2": [list(x) for x in TRUTH["top3"]],
    "T3": [list(x) for x in TRUTH["trend"]],
}
PLAN = {"tasks": [{"id": t, "output": o, "instruction": f"Produce {o} from penjualan.csv exactly."}
                  for t, o in (("T1", "data_check"), ("T2", "top3"), ("T3", "trend"))]}
KEYS = {"ANTHROPIC_API_KEY": "x", "ARGUS_FAKE_SCRIPT": "x"}


def _reply(tool, args, id):
    return {"tool_calls": [{"name": tool, "args": args, "id": id}], "usage": {"input_tokens": 500, "output_tokens": 50}}


def fake_cfg(max_usd=5.0):
    cfg = copy.deepcopy(load_config())
    for role in ("orchestrator", "worker", "writer", "evaluator"):   # 3e: every model-backed node, all fake
        cfg["roles"][role]["model"] = "fake:scripted"
    cfg["token_estimates"].update(orchestrator=12_000, worker=20_000)
    cfg["llm"]["base_delay"] = 0
    cfg["budget"]["max_usd"] = max_usd
    return cfg


# The writer's and the judge's prompts carry no "Task id", so they take the "default" queue after the plan.
RECS = template_recommendations(VALUES["T2"], VALUES["T3"])
CRITERIA = [c["id"] for c in SALES_REPORT["rubric"]]


def recs_reply(recs=RECS, id="w1"):
    return _reply("SubmitRecommendations", {"recommendations": recs}, id)


def verdict_reply(fail=(), id="v1"):
    items = [{"id": c, "pass": c not in fail, "evidence": [RECS[0]["text"][:40]], "reason": f"checked {c}"}
             for c in CRITERIA]
    return _reply("SubmitVerdict", {"criteria": items}, id)


def run_cli(tmp_path, cfg, *, live=True, default=None):
    (tmp_path / "config.yaml").write_text(yaml.safe_dump(cfg))
    script = {t: [_reply("ReadData", {}, "r1"), _reply("SubmitResult", {"value": v}, "s1")] for t, v in VALUES.items()}
    script["default"] = [_reply("SubmitPlan", PLAN, "p1")] + (default if default is not None
                                                               else [recs_reply(), verdict_reply()])
    (tmp_path / "script.json").write_text(json.dumps(script))
    env = {k: v for k, v in os.environ.items() if k != "ARGUS_LIVE"}
    env["ARGUS_FAKE_SCRIPT"] = str(tmp_path / "script.json")
    if live:
        env["ARGUS_LIVE"] = "1"
    cmd = [sys.executable, "scripts/smoke_live.py", "--config", str(tmp_path / "config.yaml"),
           "--run-id", "s", "--runs-dir", str(tmp_path / "runs")]
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, env=env)


# ---- gates before anything is sent -----------------------------------------------------------

def test_nothing_happens_without_argus_live(tmp_path):
    r = run_cli(tmp_path, fake_cfg(), live=False)
    assert r.returncode == 2 and "ARGUS_LIVE=1" in r.stderr
    assert not (tmp_path / "runs").exists()


@pytest.mark.parametrize("budget_usd, expected", [(5.0, 0.50), (0.20, 0.20), (None, 0.50), (math.inf, 0.50)])
def test_max_usd_is_lowered_to_the_smoke_cap_never_raised(budget_usd, expected):
    cfg = fake_cfg(max_usd=budget_usd)
    assert prepare_config(cfg, env=KEYS)["budget"]["max_usd"] == expected


def test_every_model_backed_node_is_switched_to_llm():
    # 3e: the writer (synthesize) and the judge (evaluator) run live too.
    cfg = fake_cfg()
    cfg["impl"] = {"orchestrator": "fake", "worker": "fake", "synthesize": "fake", "evaluator": "fake"}
    assert prepare_config(cfg, env=KEYS)["impl"] == {"orchestrator": "llm", "worker": "llm",
                                                      "synthesize": "llm", "evaluator": "llm"}


def test_the_judge_key_is_required_too():
    with pytest.raises(SmokeRefused, match="evaluator: environment variable DEEPSEEK_API_KEY"):
        prepare_config(copy.deepcopy(load_config()), env={"ANTHROPIC_API_KEY": "x"})


@pytest.mark.parametrize("cap", [0, -1, math.inf, None, True, "0.5"])
def test_an_invalid_smoke_cap_is_refused(cap):
    cfg = fake_cfg()
    cfg["smoke"]["max_usd"] = cap
    with pytest.raises(SmokeRefused, match="smoke.max_usd"):
        prepare_config(cfg, env=KEYS)


def test_python_only_needs_the_docker_sandbox():
    with pytest.raises(SmokeRefused, match="--python-only needs --sandbox docker"):
        prepare_config(fake_cfg(), python_only=True, env=KEYS)


def test_python_only_leaves_workers_only_run_python():
    cfg = prepare_config(fake_cfg(), sandbox="docker", python_only=True, env=KEYS, sandbox_status=(True, ""))
    assert cfg["sandbox"]["kind"] == "docker" and cfg["tools"]["worker"] == ["run_python"]
    plain = prepare_config(fake_cfg(), sandbox="docker", env=KEYS, sandbox_status=(True, ""))
    assert plain["tools"]["worker"] == ["read_data", "run_python"]


def test_unusable_sandbox_is_refused_before_anything_is_created():
    with pytest.raises(SmokeRefused, match="sandbox not usable: no daemon"):
        prepare_config(fake_cfg(), sandbox="docker", env=KEYS, sandbox_status=(False, "no daemon"))


def test_allow_unpriced_is_refused():
    cfg = fake_cfg()
    cfg["budget"]["allow_unpriced"] = True
    with pytest.raises(SmokeRefused, match="allow_unpriced"):
        prepare_config(cfg, env=KEYS)


def test_unpriced_model_is_refused():
    cfg = fake_cfg()
    cfg["roles"]["worker"]["model"] = "anthropic:claude-unpriced"
    with pytest.raises(SmokeRefused, match="no entry in 'prices'"):
        prepare_config(cfg, env=KEYS)


def test_missing_key_is_refused_before_anything_is_created(tmp_path):
    cfg = load_config()  # the real roles: anthropic models
    with pytest.raises(SmokeRefused, match="ANTHROPIC_API_KEY"):
        prepare_config(copy.deepcopy(cfg), env={})
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY",)}
    env["ARGUS_LIVE"] = "1"
    r = subprocess.run([sys.executable, "scripts/smoke_live.py", "--runs-dir", str(tmp_path / "runs")],
                       cwd=ROOT, capture_output=True, text=True, env=env)
    assert r.returncode == 2 and "ANTHROPIC_API_KEY" in r.stderr
    assert not (tmp_path / "runs").exists()


# ---- the run itself ----------------------------------------------------------------------------

def test_offline_run_end_to_end_reports_verdict_and_ledger(tmp_path):
    r = run_cli(tmp_path, fake_cfg(max_usd=5.0))
    assert r.returncode == 0, r.stderr + r.stdout
    run_dir = tmp_path / "runs" / "s"
    s = json.loads((run_dir / "smoke_summary.json").read_text())
    assert s["result"]["status"] == "DONE"
    assert [(v["passed"], v["rubric"]) for v in s["verdicts"]] == [(True, {"valid": True, "passed": True})]
    # orchestrator 1 + 3 workers x 2 steps + writer 1 + judge 1
    assert len(s["ledger"]) == 1 + 3 * 2 + 1 + 1 and all(c["status"] == "ok" for c in s["ledger"])
    assert [c["node"] for c in s["ledger"]][-2:] == ["synthesize", "evaluator"]
    assert sum(c["usd"] for c in s["ledger"]) == pytest.approx(s["result"]["usd_billed"])
    assert [w["event"] for w in s["writer"]] == ["recs_accepted"] and [j["event"] for j in s["judge"]] == ["rubric_verdict"]
    assert s["report"] and " Aksi: " in (run_dir / "laporan.md").read_text()
    assert json.loads((run_dir / "laporan.provenance.json").read_text())["recommendations"] == RECS
    start = next(json.loads(l) for l in (run_dir / "events.jsonl").read_text().splitlines()
                 if json.loads(l)["event"] == "run_start")
    assert start["budget"]["max_usd"] == 0.50                 # lowered from 5.0
    assert "== evaluator" in r.stdout and "== ledger" in r.stdout and "== writer (synthesize) and judge" in r.stdout


def _summary(tmp_path, default, **budget):
    cfg = fake_cfg()
    cfg["budget"].update(budget)
    r = run_cli(tmp_path, cfg, default=default)
    return r, json.loads((tmp_path / "runs" / "s" / "smoke_summary.json").read_text())


def test_a_criterion_the_judge_fails_keeps_the_run_from_passing(tmp_path):
    r, s = _summary(tmp_path, [recs_reply(), verdict_reply(fail=["actionable"])], max_iterations=1)
    assert r.returncode == 1 and s["result"]["status"] != "DONE"
    (v,) = s["verdicts"]
    assert v["passed"] is False and v["failures"] == ["report:rubric_actionable"]
    assert s["judge"][0]["failed"] == ["actionable"]


def test_a_judge_that_never_answers_with_the_tool_fails_closed(tmp_path):
    r, s = _summary(tmp_path, [recs_reply(), {"content": "Looks fine.", "usage": {"input_tokens": 500, "output_tokens": 5}},
                               {"content": "Pass.", "usage": {"input_tokens": 500, "output_tokens": 5}}], max_iterations=1)
    assert r.returncode == 1 and s["verdicts"][0]["failures"] == ["report:rubric_valid"]
    assert [j["event"] for j in s["judge"]] == ["verdict_rejected", "verdict_rejected", "rubric_invalid"]


def test_a_writer_that_never_grounds_its_numbers_means_no_judge_call(tmp_path):
    bad = [dict(RECS[0], text=RECS[0]["text"].replace("%", "1%")), RECS[1]]       # a number not in the facts
    r, s = _summary(tmp_path, [recs_reply(bad, id=f"w{i}") for i in range(3)], max_iterations=1)
    assert r.returncode == 1 and [w["event"] for w in s["writer"]] == ["recs_invalid"] * 3 + ["synthesize_failed"]
    assert [j["event"] for j in s["judge"]] == ["rubric_skipped"]                 # the code rejected it: not paid
    assert not [c for c in s["ledger"] if c["node"] == "evaluator"]
    assert "report:recs_count" in s["verdicts"][0]["failures"]


def test_a_failed_run_is_not_retried(tmp_path, monkeypatch):
    calls = []

    def boom(**kw):
        calls.append(kw)
        raise RuntimeError("provider down")

    monkeypatch.setenv("ARGUS_LIVE", "1")
    monkeypatch.setenv("ARGUS_FAKE_SCRIPT", "unused")
    monkeypatch.setattr(smoke_live, "run_task", boom)
    monkeypatch.setattr(smoke_live, "load_config", lambda path=None: fake_cfg())
    rc = smoke_live.main(["--runs-dir", str(tmp_path)])
    assert rc == 1 and len(calls) == 1
    assert calls[0]["max_concurrency"] == 1


# ---- serial workers --------------------------------------------------------------------------

def _peak_parallel_workers(tmp_path, monkeypatch, max_concurrency):
    lock, state = threading.Lock(), {"now": 0, "peak": 0}
    original = graph_module.make_worker

    def slow_make_worker(*a, **kw):
        inner = original(*a, **kw)

        def worker(payload):
            with lock:
                state["now"] += 1
                state["peak"] = max(state["peak"], state["now"])
            try:
                time.sleep(0.3)
                return inner(payload)
            finally:
                with lock:
                    state["now"] -= 1
        return worker

    monkeypatch.setattr(graph_module, "make_worker", slow_make_worker)
    cfg = copy.deepcopy(load_config())          # fake orchestrator and fake workers: 3 tasks
    r = run_task(goal="x", scenario="pass", run_id=f"c{max_concurrency}", runs_dir=tmp_path, cfg=cfg,
                 max_concurrency=max_concurrency)
    assert r["status"] == "DONE"
    return state["peak"]


def test_workers_run_in_parallel_by_default(tmp_path, monkeypatch):
    assert _peak_parallel_workers(tmp_path, monkeypatch, None) >= 2   # shows the probe can see overlap


def test_max_concurrency_one_runs_workers_one_at_a_time(tmp_path, monkeypatch):
    assert _peak_parallel_workers(tmp_path, monkeypatch, 1) == 1
