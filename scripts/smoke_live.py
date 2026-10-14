"""Phase 2e: one live run of the CSV task with real models (orchestrator and worker = llm).

Real money, so the script is deliberately narrow:
  - it does nothing unless ARGUS_LIVE=1;
  - budget.max_usd is lowered to smoke.max_usd when the config allows more (never raised);
  - unpriced models are refused (allow_unpriced must stay false), and every role's key must be set
    before anything is created;
  - workers run one at a time (smoke.max_concurrency);
  - exactly one run: a failure is reported, never retried.
Afterwards it prints the evaluator verdicts, the per-call ledger and where the event log is, and writes
the same summary to <run>/smoke_summary.json.

  ARGUS_LIVE=1 python scripts/smoke_live.py
  ARGUS_LIVE=1 python scripts/smoke_live.py --sandbox docker     # workers also get RunPython
"""
import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from models.registry import ConfigError, ModelRef  # noqa: E402
from runner import load_config, read_events, run_task  # noqa: E402

GOAL = "Analyze penjualan.csv: top 3 products, monthly trend, 2 recommendations -> laporan.md"
LIVE_ROLES = ("orchestrator", "worker")


class SmokeRefused(Exception):
    """The run was not started; nothing was sent and nothing was created."""


def prepare_config(cfg, *, sandbox=None, env=None):
    """Return the config for a smoke run, or raise SmokeRefused. Never raises budget.max_usd."""
    env = os.environ if env is None else env
    smoke = cfg.get("smoke") or {}
    cap = smoke.get("max_usd")
    if not isinstance(cap, (int, float)) or isinstance(cap, bool) or not 0 < cap < math.inf:
        raise SmokeRefused(f"smoke.max_usd must be a positive finite number, got {cap!r}")
    if cfg["budget"].get("allow_unpriced"):
        raise SmokeRefused("budget.allow_unpriced is true: an unpriced model could spend without a cap")

    budget_usd = cfg["budget"].get("max_usd")
    cfg["budget"]["max_usd"] = cap if budget_usd is None else min(float(budget_usd), cap)
    cfg.setdefault("impl", {}).update({role: "llm" for role in LIVE_ROLES})
    if sandbox:
        cfg.setdefault("sandbox", {})["kind"] = sandbox

    for role in LIVE_ROLES:
        ref = ModelRef.parse(cfg["roles"][role]["model"])
        if str(ref) not in (cfg.get("prices") or {}):
            raise SmokeRefused(f"{role}: model {ref} has no entry in 'prices'")
        pcfg = (cfg.get("providers") or {}).get(ref.provider)
        if pcfg is None:
            raise SmokeRefused(f"{role}: provider {ref.provider!r} is not configured")
        var = pcfg.get("api_key_env") or pcfg.get("script_env")
        if var and not env.get(var):
            raise SmokeRefused(f"{role}: environment variable {var} is not set")
    return cfg


def ledger(events):
    """One row per model call attempt, in order (refused calls included: they were never sent)."""
    rows = []
    for e in events:
        if e["event"] != "llm_call":
            continue
        rows.append({k: e.get(k) for k in ("node", "task", "iteration", "step", "attempt", "model", "status",
                                           "input_tokens", "output_tokens", "cache_read", "tokens", "usd",
                                           "charged", "latency_s", "error")})
    return rows


def summarize(result, run_dir):
    events = read_events(run_dir / "events.jsonl")
    verdicts = [{k: e.get(k) for k in ("iteration", "score", "passed", "failures", "status", "stop_reason")}
                for e in events if e["event"] == "eval_verdict"]
    report = run_dir / "laporan.md"
    return {
        "result": result,
        "verdicts": verdicts,
        "ledger": ledger(events),
        "plans": [{k: e.get(k) for k in ("event", "revision", "attempt", "tasks", "outputs", "errors")}
                  for e in events if e["event"] in ("spec_created", "spec_revised", "plan_invalid")],
        "warnings": [e for e in events if e["event"] in ("config_warning", "estimate_miss", "budget_violation",
                                                          "orchestrator_stop", "run_error")],
        "report": str(report) if report.exists() else None,
        "events": str(run_dir / "events.jsonl"),
    }


def print_summary(s, cfg):
    r = s["result"]
    print(f"\n== smoke run {r['run_id']}: {r['status']} ({r.get('stop_reason') or '-'})")
    print(f"budget.max_usd {cfg['budget']['max_usd']} | billed ${r['usd_billed']:.6f} "
          f"(complete: {r['usd_complete']}) | calls {r['llm_calls']} | iterations {r['iteration']}")
    print("\n== evaluator")
    for v in s["verdicts"] or [{"iteration": "-", "score": "-", "passed": "-", "failures": "no verdict"}]:
        print(f"  iteration {v['iteration']}: score {v['score']} passed {v['passed']} failures {v['failures']}")
    print("\n== ledger (llm_call)")
    for c in s["ledger"]:
        where = c["node"] + (f"/{c['task']}" if c.get("task") else "") + \
            (f" step {c['step']}" if c.get("step") is not None else "")
        print(f"  {where:<28} it {c['iteration']} #{c['attempt']} {c['status']:<15} "
              f"in {c['input_tokens']} out {c['output_tokens']} ${c['usd'] or 0:.6f} {c['charged'] or ''}"
              + (f"  {c['error']}" if c.get("error") else ""))
    for w in s["warnings"]:
        print(f"  ! {w['event']}: {w.get('message') or w.get('reason') or w.get('error') or ''}")
    print(f"\nreport: {s['report'] or '(not written)'}\nevents: {s['events']}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", help="config file (default: config.yaml)")
    ap.add_argument("--run-id", default=time.strftime("smoke_%Y%m%d_%H%M%S"))
    ap.add_argument("--runs-dir", default=str(ROOT / "runs"))
    ap.add_argument("--sandbox", choices=["docker"], help="give workers RunPython in the Docker sandbox")
    a = ap.parse_args(argv)

    if os.environ.get("ARGUS_LIVE") != "1":
        print("refused: set ARGUS_LIVE=1 to run against real models (this spends money)", file=sys.stderr)
        return 2
    if a.sandbox and not os.environ.get("ARGUS_SANDBOX_IMAGE") and (ROOT / ".sandbox_image").exists():
        os.environ["ARGUS_SANDBOX_IMAGE"] = (ROOT / ".sandbox_image").read_text().strip()
    try:
        cfg = prepare_config(load_config(a.config), sandbox=a.sandbox)
    except (SmokeRefused, ConfigError, KeyError) as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2

    max_conc = int((cfg.get("smoke") or {}).get("max_concurrency", 1))
    print(f"smoke: orchestrator={cfg['roles']['orchestrator']['model']} worker={cfg['roles']['worker']['model']} "
          f"max_usd={cfg['budget']['max_usd']} max_concurrency={max_conc} sandbox={cfg['sandbox'].get('kind')}")
    try:  # exactly one attempt: no retry on any outcome
        result = run_task(goal=GOAL, scenario="pass", run_id=a.run_id, runs_dir=a.runs_dir, cfg=cfg,
                          echo=False, max_concurrency=max_conc)
    except Exception as e:
        print(f"run failed: {type(e).__name__}: {e} (not retried)", file=sys.stderr)
        run_dir = Path(a.runs_dir) / a.run_id
        if (run_dir / "events.jsonl").exists():
            print(f"events: {run_dir / 'events.jsonl'}", file=sys.stderr)
        return 1

    run_dir = Path(a.runs_dir) / a.run_id
    s = summarize(result, run_dir)
    (run_dir / "smoke_summary.json").write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    print_summary(s, cfg)
    return 0 if result["status"] == "DONE" else 1


if __name__ == "__main__":
    sys.exit(main())
