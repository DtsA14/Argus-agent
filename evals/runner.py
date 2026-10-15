"""Run manifest tasks and write a report (docs/reviews/EVAL_SET_V1.md, section 6).

Modes:
  reference  each task's reference script (scripted model): validates the benchmark; the eval must pass
  wrong      each task's wrong or cheating script: validates the benchmark; the eval must NOT pass
  live       the configured coder model (real money; the CLI requires ARGUS_LIVE=1 and a total cap)

Every task runs as its own code-task run (run id <mode>_<task>) with validation in the Docker sandbox, then is scored
independently (evals/score.py). The report records the benchmark hash and the agent version (commit, model, system
prompt hash, code_task config), so results of different agent or benchmark versions are never mixed up.
"""
import hashlib
import json
import subprocess
from pathlib import Path

from codetask.agent import system_prompt
from codetask.run import run_code_task
from codetask.tools import offered
from models.fake import ScriptedChatModel, item_from_json

from .score import aggregate, independent_checks, run_stats, score

ROOT = Path(__file__).resolve().parent.parent
MODES = ("reference", "wrong", "live")
# A task that ends like this says the infrastructure or the budget failed, not the agent: the eval stops, and every
# remaining task is reported as not run (a report row only; no run is created for it). FAILED_ACCEPTANCE is data
# about the agent and never stops the eval.
STOP_ON = ("BLOCKED", "FAILED_BUDGET")


def _sha_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def benchmark_hash(manifest_path):
    """One hash over the manifest, every task's contract and every file of its input repository (LF line endings,
    bytecode caches excluded), so any change to the benchmark is a new version."""
    manifest_path = Path(manifest_path)
    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    h = hashlib.sha256()

    def add(rel):
        p = ROOT / rel                          # an absolute rel (a manifest outside the repo) stays absolute
        h.update(rel.encode("utf-8") + b"\0" + p.read_bytes().replace(b"\r\n", b"\n") + b"\0")

    mp = manifest_path.resolve()
    add(mp.relative_to(ROOT).as_posix() if mp.is_relative_to(ROOT) else mp.as_posix())
    for t in sorted(m["tasks"], key=lambda t: t["id"]):
        add(t["contract"])
        contract = json.loads((ROOT / t["contract"]).read_text(encoding="utf-8"))
        repo = ROOT / contract["inputs"]["workspace"]
        for f in sorted(p for p in repo.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
            add(f.relative_to(ROOT).as_posix())
    return h.hexdigest()


def agent_version(cfg):
    role = cfg["code_task"]["role"]
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True,
                                    text=True).stdout.strip())
    except OSError:
        commit, dirty = None, None
    return {"commit": commit, "dirty": dirty, "model": cfg["roles"][role]["model"],
            "system_prompt_sha256": _sha_text(system_prompt(offered((cfg.get("tools") or {}).get(role, [])))),
            "code_task": cfg["code_task"]}


def load_manifest(path):
    m = json.loads(Path(path).read_text(encoding="utf-8"))
    ids = [t["id"] for t in m["tasks"]]
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate task ids in {path}")
    return m


def run_eval(manifest_path, mode, runs_dir, cfg, *, tasks=None, max_total_usd=None, validate=None):
    """Run the tasks, score them, and return the report. live needs max_total_usd: a task starts only if what the
    eval has spent so far plus that task's contract cap still fits."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    if mode == "live" and max_total_usd is None:
        raise ValueError("live mode needs max_total_usd")
    m = load_manifest(manifest_path)
    selected = [t for t in m["tasks"] if tasks is None or t["id"] in tasks]
    if tasks is not None and {t["id"] for t in selected} != set(tasks):
        raise ValueError(f"unknown tasks: {sorted(set(tasks) - {t['id'] for t in selected})}")
    cfg = {**cfg, "sandbox": {**(cfg.get("sandbox") or {}), "kind": "docker"}}
    if mode != "live":     # scripted: priced and recorded as the fake model, never as the configured real one
        role = cfg["code_task"]["role"]
        cfg = {**cfg, "roles": {**cfg["roles"], role: {**cfg["roles"][role], "model": "fake:scripted"}}}
    runs_dir = Path(runs_dir)
    rows, spent, stopped = [], 0.0, None

    def not_run(t, why):
        return {"id": t["id"], "category": t["category"], "expected": t["expected"], "status": None,
                "eval_pass": False, "honest": None, "acceptance_pass": None if t["expected"] != "DONE" else False,
                "why": [f"not run: {why}"], "not_run": True}

    for t in selected:
        if stopped:
            rows.append(not_run(t, f"the eval stopped after {stopped['task']} ended {stopped['status']}"))
            continue
        contract = json.loads((ROOT / t["contract"]).read_text(encoding="utf-8"))
        if mode == "live" and spent + float(contract["limits"]["max_usd"]) > max_total_usd + 1e-12:
            rows.append(not_run(t, f"total cap ${max_total_usd} would not fit"))
            continue
        models = None
        if mode != "live":
            models = {cfg["code_task"]["role"]: ScriptedChatModel(script=[item_from_json(x) for x in t[mode]])}
        run_id = f"{mode}_{t['id']}"
        run_code_task(contract_path=ROOT / t["contract"], run_id=run_id, runs_dir=runs_dir, cfg=cfg, models=models,
                      validate=validate)
        checks = independent_checks(contract, runs_dir / run_id, cfg["sandbox"], **({"validate": validate}
                                                                                    if validate else {}))
        row = score(t, checks)
        row["stats"] = run_stats(runs_dir / run_id)
        row["checks"] = {k: checks[k] for k in ("stop_reason", "blocked_reason", "protected_changed", "outside_scope",
                                                "summary_valid", "false_claims", "fresh_validations")}
        if mode == "wrong":
            row["benchmark_ok"] = not row["eval_pass"]     # a wrong or cheating script must never pass
        elif mode == "reference":
            row["benchmark_ok"] = row["eval_pass"]
        spent += row["stats"]["usd_billed"] or 0.0
        rows.append(row)
        if row["status"] in STOP_ON:
            stopped = {"task": t["id"], "status": row["status"], "blocked_reason": checks["blocked_reason"]}
    report = {"benchmark": m["version"], "benchmark_sha256": benchmark_hash(manifest_path), "mode": mode,
              "agent": agent_version(cfg), "tasks": rows, "stopped": stopped,
              "ran": sum(not r.get("not_run") for r in rows), "not_run": sum(bool(r.get("not_run")) for r in rows),
              "usd_spent": round(spent, 6), "summary": aggregate([r for r in rows if not r.get("not_run")])}
    if mode != "live":
        report["benchmark_valid"] = all(r.get("benchmark_ok") for r in rows)
    return report
