import json
from pathlib import Path

import yaml
from langgraph.checkpoint.sqlite import SqliteSaver

from graph import build_graph
from harness.errors import BudgetExceeded, EstimateExceeded
from harness.events import EventLog
from harness.llm import reconcile_ledger
from models.registry import role_warnings

ROOT = Path(__file__).parent


def load_config(path=None):
    with open(path or ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


class RunExists(Exception):
    """A fresh run was asked for an id that already has state; resume it or pick a new id."""


def actual_spend(events_path):
    """Tokens of work actually performed, including work redone after a crash (sum of body_done)."""
    total = 0
    for line in Path(events_path).read_text(encoding="utf-8").splitlines():
        e = json.loads(line)
        if e["event"] == "body_done":
            total += e.get("tokens", 0)
    return total


def read_events(events_path):
    return [json.loads(l) for l in Path(events_path).read_text(encoding="utf-8").splitlines()]


def ledger_totals(events_path):
    """Reconciled model spend: every attempt, plus calls cut off by a crash at their worst case."""
    return reconcile_ledger(read_events(events_path))[1]


def run_task(*, goal="", scenario="pass", run_id, runs_dir, cfg,
             crash_at=None, resume=False, echo=False):
    run_dir = Path(runs_dir) / run_id
    if not resume and (run_dir / "checkpoints.sqlite").exists():
        # A stale checkpoint or memo would silently leak old results into the new run.
        raise RunExists(f"run '{run_id}' already exists in {runs_dir}; use --resume or a new --run-id")
    if resume and not (run_dir / "checkpoints.sqlite").exists():
        raise RunExists(f"nothing to resume: run '{run_id}' has no checkpoint in {runs_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)
    log = EventLog(run_dir / "events.jsonl", echo=echo)
    # One iteration = 4 supersteps (orchestrator, parallel workers, synthesize, evaluator). The limit must
    # follow max_iterations, or raising max_iterations crashes with GraphRecursionError instead of
    # stopping cleanly on the budget.
    steps = 4 * int(cfg["budget"]["max_iterations"]) + 10
    config = {"configurable": {"thread_id": run_id}, "recursion_limit": steps}

    with SqliteSaver.from_conn_string(str(run_dir / "checkpoints.sqlite")) as cp:
        graph = build_graph(cfg, run_dir, log, cp, crash_at=crash_at)
        try:
            if resume:
                log.emit("resume", run_id=run_id)
                graph.invoke(None, config, durability="sync")
            else:
                log.emit("run_start", run_id=run_id, scenario=scenario, budget=cfg["budget"],
                         roles={r: c["model"] for r, c in cfg.get("roles", {}).items()})
                for w in role_warnings(cfg):
                    log.emit("config_warning", message=w)
                graph.invoke(
                    {
                        "goal": goal, "scenario": scenario, "run_id": run_id,
                        "iteration": 0, "tokens_used": 0, "usd_used": 0.0, "elapsed_s": 0.0,
                        "stale_rounds": 0, "best_score": -1.0, "status": "RUNNING",
                    },
                    config,
                    # "sync": checkpoint is on disk before the next step starts.
                    # The default "async" can lose the last checkpoint on a hard crash.
                    durability="sync",
                )
            final = dict(graph.get_state(config).values)
        except BudgetExceeded as e:
            final = {**dict(graph.get_state(config).values),
                     "status": "FAILED_BUDGET", "stop_reason": e.reason}
        except EstimateExceeded as e:
            # A node spent more than it reserved (e.g. a provider billed more input than estimated).
            # The money is already spent: stop cleanly and report it; usd_billed holds the real figure.
            log.emit("budget_violation", source="node", error=str(e))
            final = {**dict(graph.get_state(config).values),
                     "status": "FAILED_BUDGET", "stop_reason": f"budget_violation: {e}"}
        except Exception as e:
            log.emit("run_error", error=repr(e))
            raise

    result = {k: final.get(k) for k in ("status", "stop_reason", "iteration", "tokens_used", "scenario")}
    result["elapsed_s"] = round(final.get("elapsed_s", 0.0), 3)
    result["run_id"] = run_id
    # tokens_used: what the run accounts for (each node run once).
    # tokens_spent: work actually performed; higher only if a crash forced work to be redone.
    result["tokens_spent"] = actual_spend(run_dir / "events.jsonl")
    # usd_used: accounted USD in state; usd_billed: sum of every model call attempt in the ledger
    # (llm_call events), including failed attempts and work redone after a crash.
    result["usd_used"] = final.get("usd_used", 0.0) or 0.0
    totals = ledger_totals(run_dir / "events.jsonl")
    result["usd_billed"] = totals["usd"]                 # full precision, reconciled
    result["usd_complete"] = totals["usd_complete"]       # False if an unpriced model was used
    result["llm_calls"] = totals["calls"]
    result["llm_calls_unknown"] = totals["unknown_after_crash"]
    result["budget_violations"] = sum(e["event"] == "budget_violation" for e in read_events(run_dir / "events.jsonl"))
    (run_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    log.emit("run_end", **result)
    return result
