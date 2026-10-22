"""The code-task run: setup -> attempt -> acceptance -> (attempt -> acceptance)* -> end.

  setup       freeze the contract (<run>/contract.json + sha256), copy the input repository to <run>/workspace,
              check the scope against it, check the sandbox, and admit attempt 0
  attempt     one agent attempt (codetask/agent.py); status stays RUNNING unless the contract changed
  acceptance  the verdict from evidence (acceptance/verdict.py), written to <run>/verdict_<i>.json, then the next
              status: DONE, BLOCKED, another attempt, or FAILED_ACCEPTANCE

Budget: the ledger (llm_call_started / llm_call in events.jsonl) is the source of truth, never the checkpoint. An
attempt is admitted only if everything the ledger shows spent (calls cut off by a crash at their worst case) plus the
attempt's whole reservation fits the run's limits, and the attempt's reservation is itself restored from the ledger.
So resuming can never give back money that was spent, and the run cannot exceed max_usd however often it crashes
(given exact input counts; see harness/llm.py for heuristic counts).

Every node runs under harness.guard: its result is committed to the memo before it is handed to LangGraph, and a
committed result is never recomputed. Checkpoints use durability="sync".
"""
import json
import math
import operator
import os
import shutil
import subprocess
from pathlib import Path
from typing import Annotated, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from acceptance import contract as ct
from acceptance import intake
from acceptance.validation import run_validation
from acceptance.verdict import evaluate
from acceptance.workspace import digest, prepare
from harness.crash import Crasher
from harness.errors import EstimateExceeded
from harness.events import EventLog, TaggedLog
from harness.guard import guard
from harness.llm import LLMCaller, check_long_context, reconcile_ledger, to_nano
from harness.memo import Memo
from models.registry import ModelRef, price_for

from . import frozen
from . import status as st
from .agent import feedback_from, make_attempt
from .tools import Toolbox

ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = "workspace"


class RunExists(Exception):
    pass


def argus_provenance():
    """The Argus commit running the agent and whether its tracked files were changed. None when unknown."""
    try:
        commit = intake.git(ROOT, "rev-parse", "HEAD").decode().strip()
        dirty = bool(intake.git(ROOT, "status", "--porcelain", "--untracked-files=no").strip())
    except (intake.IntakeError, OSError, subprocess.SubprocessError):
        return {"commit": None, "dirty": None}
    return {"commit": commit, "dirty": dirty}


class State(TypedDict, total=False):
    run_id: str
    contract_path: str
    contract_sha: str
    before: dict                 # snapshot of the workspace as copied, before the agent ran
    iteration: int               # the attempt that runs next (or ran last)
    attempt: dict                # how the last attempt ended
    verdict: dict                # outcome and failing criteria of the last verdict
    failures: list               # failing criterion ids, one list per attempt
    feedback: object             # {unmet, checks} from the last verdict (a list in older checkpoints)
    status: str
    stop_reason: str
    blocked_reason: str
    tools: list                  # the effective tool allowlist of this run (config + frozen contract)
    provenance: dict             # input (workspace, snapshot hash, intake record) and the Argus commit, at setup
    budget_profile: dict         # the profile the run was configured with: name, attempt_tokens, max_output_tokens
    loop_policy: dict            # D3, frozen at setup: auto_validate, auto_validate_max (absent: a run from before D3)
    tokens_used: Annotated[int, operator.add]
    usd_used: Annotated[float, operator.add]
    elapsed_s: Annotated[float, operator.add]


USD_PROFILE_KEYS = ("attempt_usd", "max_input_tokens")   # D1: optional in a profile; absent, the run is as before


def apply_profile(cfg, name):
    """The config with a budget profile applied: the attempt reservation and the coder's output cap, nothing else.
    The cost cap (budget.max_usd, the contract's limits.max_usd) is never touched. Unknown names raise KeyError."""
    p = cfg["code_task"]["profiles"][name]
    role = cfg["code_task"]["role"]
    task = {k: v for k, v in cfg["code_task"].items() if k not in USD_PROFILE_KEYS}   # nothing leaks from a profile
    task.update({k: p[k] for k in USD_PROFILE_KEYS if p.get(k) is not None})         # applied before (D1)
    out = {**cfg, "code_task": {**task, "attempt_tokens": int(p["attempt_tokens"]), "applied_profile": name},
           "roles": {**cfg["roles"], role: {**cfg["roles"][role], "max_output_tokens": int(p["max_output_tokens"])}}}
    return out


def contract_profile(path):
    """The budget profile a contract file names, or None (also when the file is unreadable: setup reports that)."""
    try:
        c = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return c.get("budget_profile") if isinstance(c, dict) else None


def settings(cfg, contract=None):
    """Run limits: the stricter of config and contract."""
    c = cfg["code_task"]
    role = cfg["roles"][c["role"]]
    ref = ModelRef.parse(role["model"])
    price = price_for(cfg, ref)
    if price is None:
        raise ct.ContractError([f"coder model {ref} has no price: its cost could not be capped"])
    rate = max(price["input"], price["output"], price.get("cache_write_5m") or 0) * price.get("peak_multiplier", 1) / 1_000_000
    tokens = int(c["attempt_tokens"])
    max_usd = cfg["budget"].get("max_usd")
    max_usd = math.inf if max_usd is None else float(max_usd)
    # D1: a profile may reserve the attempt in USD; otherwise its tokens are priced as if all were output
    attempt_usd = float(c["attempt_usd"]) if c.get("attempt_usd") is not None else tokens * rate
    max_input = None if c.get("max_input_tokens") is None else int(c["max_input_tokens"])
    check_long_context(cfg, ref, tokens if max_input is None else max_input, f"code task (role {c['role']!r})")
    out = {"attempt_tokens": tokens, "attempt_usd": attempt_usd, "max_input_tokens": max_input,
           "max_steps": int(c["max_steps"]),
           "stagnation_rounds": int(c.get("stagnation_rounds", 2)),
           "max_tokens": int(cfg["budget"]["max_tokens"]), "max_usd": max_usd, "max_iterations": None}
    if contract is not None:
        out["max_usd"] = min(out["max_usd"], float(contract["limits"]["max_usd"]))
        out["max_iterations"] = int(contract["limits"]["max_iterations"])
    return out


def cache_totals(events, cfg):
    """D5: cache tokens of the run's model calls and an ESTIMATE of what caching saved (the same calls priced as plain
    input, minus what the ledger charged). cache_creation_tokens is None when no call reported such a thing."""
    from datetime import datetime, timezone
    from models.pricing import cost_usd
    read, creation, saved = 0, None, 0
    for e in events:
        if e.get("event") != "llm_call" or e.get("status") != "ok":
            continue
        read += e.get("cache_read") or 0
        if e.get("cache_creation") is not None:
            creation = (creation or 0) + e["cache_creation"]
        price = cfg.get("prices", {}).get(e.get("model"))
        plain = cost_usd(price, input_tokens=e.get("input_tokens") or 0, output_tokens=e.get("output_tokens") or 0,
                         window=cfg.get("peak_windows", {}).get(str(e.get("model")).split(":")[0]),
                         now=datetime.fromtimestamp(e["ts"], timezone.utc))
        if plain is not None and e.get("usd_nano") is not None:
            saved += to_nano(plain) - e["usd_nano"]
    return {"cache_read_tokens": read, "cache_creation_tokens": creation, "usd_saved_estimate": saved / 1e9}


def admission(log, lim):
    """Name of the limit that forbids one more attempt, or None. Spend comes from the ledger only."""
    _, totals = reconcile_ledger(log.read())
    if totals["tokens"] + lim["attempt_tokens"] > lim["max_tokens"]:
        return "max_tokens"
    if math.isfinite(lim["max_usd"]) and totals["usd_nano"] + to_nano(lim["attempt_usd"]) > to_nano(lim["max_usd"]):
        return "max_usd"
    return None


def build_graph(cfg, run_dir, log, checkpointer, *, crash_at=None, models=None, validate=None, preflight=None,
                env_preflight=None, root=None):
    """validate / preflight / env_preflight: injected by tests to run without Docker (default: the real sandbox).
    root: where the contract's input repository and its intake record live (a router job has its own); None is this
    checkout (ROOT, read when called)."""
    run_dir, root = Path(run_dir), Path(ROOT if root is None else root)
    ws = run_dir / WORKSPACE
    memo = Memo(run_dir / "memo.sqlite")
    crasher = Crasher(crash_at, str(run_dir / ".crashed"), log)
    scfg = dict(cfg.get("sandbox") or {})
    validate = validate or run_validation
    if preflight is None:
        from tools import sandbox as sb
        preflight = lambda: sb.status(scfg)   # noqa: E731
    if env_preflight is None:
        from tools import sandbox as sb
        env_preflight = lambda name: sb.status({**scfg, "environment": name})   # noqa: E731
    lim0 = settings(cfg)
    caller = LLMCaller(cfg, cfg["code_task"]["role"], log, model=(models or {}).get(cfg["code_task"]["role"]))
    from tools.sandbox import tool_version
    versions = {"ListFiles": "1", "SearchFiles": "1", "ReadFile": "1", "WriteFile": "1", "EditFile": "1", "Finish": "1",
                "RunValidation": f"1:{tool_version(scfg)}"}
    attempt_fn = make_attempt(caller, memo, log, tokens=lim0["attempt_tokens"], usd=lim0["attempt_usd"],
                              max_steps=lim0["max_steps"], tool_versions=versions, crasher=crasher,
                              max_input=lim0["max_input_tokens"])
    configured = list((cfg.get("tools") or {}).get(cfg["code_task"]["role"], []))

    def effective_tools(contract):
        """The configured allowlist plus what the frozen contract adds (contract tools are validated at setup)."""
        return configured + [t for t in ct.contract_tools(contract) if t not in configured]
    common = dict(log=log, retry=cfg["retry"], memo=memo, crash_at=crash_at, crash_marker=str(run_dir / ".crashed"))

    def move(state, new, *, reason=None, blocked=None, **extra):
        out = {"status": st.transition(state.get("status"), new, blocked)}
        if reason is not None:
            out["stop_reason"] = reason
        if blocked is not None:
            out["blocked_reason"] = blocked
        log.emit("status", old=state.get("status"), new=new, reason=reason, blocked_reason=blocked)
        return {**out, **extra}

    def setup(state):
        try:
            contract = json.loads(Path(state["contract_path"]).read_text(encoding="utf-8"))
            sha = frozen.freeze_to(run_dir, contract)
        except (OSError, ValueError, ct.ContractError) as e:
            return move(state, st.BLOCKED, reason=f"invalid contract: {e}", blocked="invalid_contract")
        log.emit("contract_frozen", sha256=sha, contract=contract["contract"], version=contract["version"])
        profile = contract.get("budget_profile")
        if profile is not None and profile not in (cfg["code_task"].get("profiles") or {}):
            return move(state, st.BLOCKED, reason=f"unknown budget profile {profile!r} "
                        f"(configured: {sorted(cfg['code_task'].get('profiles') or {})})", blocked="invalid_contract")
        if profile != cfg["code_task"].get("applied_profile"):
            return move(state, st.BLOCKED, reason=f"the frozen contract names budget profile {profile!r}, but the "
                        f"run was configured with {cfg['code_task'].get('applied_profile')!r}",
                        blocked="contract_changed")
        log.emit("tools_effective", tools=effective_tools(contract), from_contract=ct.contract_tools(contract))
        try:
            record = intake.record_for(contract["inputs"]["workspace"], root)
        except intake.IntakeError as e:
            return move(state, st.BLOCKED, reason=str(e), blocked="invalid_contract")
        if record is not None:        # an intake: the input must still be exactly the commit that was taken in
            problems = intake.check(record, root / contract["inputs"]["workspace"])
            if problems:
                return move(state, st.BLOCKED, reason="input repository changed since intake: " + "; ".join(problems),
                            blocked="invalid_contract")
            if record.get("kind") == "task" and record.get("contract_sha256") != sha:   # M6 W2a: an approved task
                return move(state, st.BLOCKED, reason="the contract is not the one approved for this task "
                            f"(sha256 {sha[:12]}, approved {str(record.get('contract_sha256'))[:12]})",
                            blocked="invalid_contract")
        if ws.exists():
            shutil.rmtree(ws)     # a copy from a setup that crashed before committing; the agent never ran on it
        try:
            before = prepare(root / contract["inputs"]["workspace"], ws)
        except (OSError, ValueError, RuntimeError) as e:
            return move(state, st.BLOCKED, reason=f"invalid input repository: {e}", blocked="invalid_contract")
        crasher.point("setup@after_copy")
        problems = ct.check_scope_against(contract, before)
        if problems:
            return move(state, st.BLOCKED, reason="; ".join(problems), blocked="invalid_contract")
        configured_envs = scfg.get("environments") or {}
        unknown = [n for n in ct.environments(contract) if n not in configured_envs]
        if unknown:                     # the contract names an environment this config does not have: fail closed
            return move(state, st.BLOCKED, reason=f"unknown sandbox environment(s) {unknown} "
                        f"(configured: {sorted(configured_envs)})", blocked="invalid_contract")
        ok, why = preflight()
        if not ok:
            return move(state, st.BLOCKED, reason=f"sandbox unavailable: {why}", blocked="sandbox_unavailable")
        for name in ct.environments(contract):
            ok, why = env_preflight(name)
            if not ok:
                return move(state, st.BLOCKED, reason=f"sandbox environment {name!r} unavailable: {why}",
                            blocked="sandbox_unavailable")
        blocker = admission(log, settings(cfg, contract))
        if blocker:
            return move(state, st.FAILED_BUDGET, reason=f"{blocker}: not even one attempt fits")
        log.emit("workspace_prepared", files=len(before))
        provenance = {"input": {"workspace": contract["inputs"]["workspace"], "snapshot_sha256": digest(before),
                                "intake": None if record is None else
                                {**{k: record.get(k) for k in ("name", "repo", "commit", "tree", "exclude")},
                                 **{k: record[k] for k in ("kind", "base", "added", "contract_sha256") if k in record}}},
                      "argus": argus_provenance()}
        log.emit("provenance", **provenance)
        budget = {"name": profile, "attempt_tokens": lim0["attempt_tokens"],
                  "max_output_tokens": int(cfg["roles"][cfg["code_task"]["role"]].get("max_output_tokens", 2048)),
                  **{k: cfg["code_task"][k] for k in USD_PROFILE_KEYS if cfg["code_task"].get(k) is not None}}
        log.emit("budget_profile", **budget)
        policy = {"auto_validate": bool(cfg["code_task"].get("auto_validate", False)),
                  "auto_validate_max": int(cfg["code_task"].get("auto_validate_max", 4))}
        log.emit("loop_policy", **policy)
        return move(state, st.RUNNING, contract_sha=sha, before=before, iteration=0, failures=[], feedback=[],
                    tools=effective_tools(contract), provenance=provenance, budget_profile=budget, loop_policy=policy)

    def agent(state):
        try:
            contract = frozen.load(run_dir, state["contract_sha"])
        except frozen.ContractChanged as e:
            return move(state, st.BLOCKED, reason=str(e), blocked="contract_changed")
        if contract.get("budget_profile") != cfg["code_task"].get("applied_profile"):   # e.g. a resume configured
            return move(state, st.BLOCKED, reason="the run is configured with budget profile "     # differently
                        f"{cfg['code_task'].get('applied_profile')!r}, the frozen contract names "
                        f"{contract.get('budget_profile')!r}", blocked="contract_changed")
        # The allowlist frozen at setup, not the config of this process: a resume with a changed config must not
        # change the agent's tools. A checkpoint without it cannot say what the run was allowed, so it stops.
        tools = state.get("tools")
        if tools is None:
            return move(state, st.BLOCKED, reason="the checkpoint has no frozen tool allowlist",
                        blocked="invalid_contract")
        if effective_tools(contract) != tools:
            log.emit("tools_config_changed", frozen=tools, current=effective_tools(contract))
        # RunValidation results are memo-keyed by the images that ran them, environments included (a contract
        # without environments keeps the key it always had).
        versions["RunValidation"] = f"1:{tool_version(scfg, ct.environments(contract))}"
        box = Toolbox(str(ws), contract, scfg, tools, log, validate=validate, journal=run_dir / "tool_journal.jsonl",
                      crasher=crasher)
        # The policy frozen at setup, not this process's config: a resume must decide every step as the run did.
        a = attempt_fn(contract, box, state["iteration"], state.get("feedback") or None,
                       policy=state.get("loop_policy"))
        return {"attempt": {"iteration": state["iteration"], "end": a["end"], "steps": a["steps"]},
                "tokens_used": a["tokens_used"], "usd_used": a["usd_used"]}

    def acceptance(state):
        try:
            contract = frozen.load(run_dir, state["contract_sha"])
        except frozen.ContractChanged as e:
            return move(state, st.BLOCKED, reason=str(e), blocked="contract_changed")
        i = state["iteration"]
        v = evaluate(contract, str(ws), state["before"], scfg, log,
                     run=lambda spec, w, c, lg=None: validate(spec, w, c, lg and TaggedLog(lg, origin="acceptance")))
        path = run_dir / f"verdict_{i}.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(v, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        os.replace(tmp, path)
        failing = sorted(c["id"] for c in v["criteria"] if c["status"] != "pass")
        log.emit("acceptance_verdict", iteration=i, outcome=v["outcome"], failing=failing,
                 workspace_digest=v["workspace_digest"])
        crasher.point("acceptance@after_verdict", iteration=i)
        summary = {"iteration": i, "outcome": v["outcome"], "failing": failing,
                   "workspace_digest": v["workspace_digest"]}
        history = list(state.get("failures") or []) + [failing]
        if v["outcome"] == "pass":
            return move(state, st.DONE, reason="all criteria passed", verdict=summary, failures=history)
        if v["outcome"] == "blocked":
            why = "; ".join(c["reason"] for c in v["criteria"] if c["status"] == "blocked")
            return move(state, st.BLOCKED, reason=why, blocked="sandbox_unavailable", verdict=summary,
                        failures=history)
        if (state.get("attempt") or {}).get("end") == "llm_failed":
            return move(state, st.BLOCKED, reason="the model provider failed during the attempt",
                        blocked="provider_failed", verdict=summary, failures=history)
        lim = settings(cfg, contract)
        n = lim["stagnation_rounds"]
        if i + 1 >= lim["max_iterations"]:
            stop = "max_iterations"
        elif len(history) >= n and all(h == failing for h in history[-n:]):
            stop = f"stagnant: the same criteria failed {n} attempts in a row"
        else:
            stop = admission(log, lim)
        if stop:
            return move(state, st.FAILED_ACCEPTANCE, reason=stop, verdict=summary, failures=history)
        return move(state, st.RUNNING, iteration=i + 1, verdict=summary, failures=history,
                    feedback=feedback_from(v, excerpts=bool(cfg["code_task"].get("feedback_error_excerpt", True))))

    g = StateGraph(State)
    lim = settings(cfg)
    g.add_node("setup", guard("setup", setup, **common))
    g.add_node("agent", guard("agent", agent, estimate=lim["attempt_tokens"], usd_estimate=lim["attempt_usd"],
                              **common))
    g.add_node("acceptance", guard("acceptance", acceptance, **common))
    running = lambda s: s["status"] == st.RUNNING   # noqa: E731
    g.add_edge(START, "setup")
    g.add_conditional_edges("setup", lambda s: "agent" if running(s) else END, ["agent", END])
    g.add_conditional_edges("agent", lambda s: "acceptance" if running(s) else END, ["acceptance", END])
    g.add_conditional_edges("acceptance", lambda s: "agent" if running(s) else END, ["agent", END])
    return g.compile(checkpointer=checkpointer)


def run_code_task(*, contract_path, run_id, runs_dir, cfg, resume=False, crash_at=None, models=None,
                  validate=None, preflight=None, env_preflight=None, echo=False, root=None):
    run_dir = Path(runs_dir) / run_id
    if not resume and (run_dir / "checkpoints.sqlite").exists():
        raise RunExists(f"run '{run_id}' already exists in {runs_dir}; resume it or pick a new run id")
    if resume and not (run_dir / "checkpoints.sqlite").exists():
        raise RunExists(f"nothing to resume: run '{run_id}' has no checkpoint in {runs_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)
    log = EventLog(run_dir / "events.jsonl", echo=echo)
    cfg = {**cfg, "sandbox": {**(cfg.get("sandbox") or {}), "labels": {"argus.run": run_id}}}
    # The budget profile shapes the caller and the attempts, which are built before setup reads the contract: take it
    # from the frozen contract on resume, from the contract file otherwise. Setup and the agent node check that the
    # frozen contract names the same profile; an unknown one is applied nowhere and blocks in setup.
    profile = contract_profile(run_dir / frozen.FILE if resume else contract_path)
    if profile is not None and profile in (cfg["code_task"].get("profiles") or {}):
        cfg = apply_profile(cfg, profile)
    config = {"configurable": {"thread_id": run_id}, "recursion_limit": 3 * 10 + 10}

    with SqliteSaver.from_conn_string(str(run_dir / "checkpoints.sqlite")) as cp:
        graph = build_graph(cfg, run_dir, log, cp, crash_at=crash_at, models=models, validate=validate,
                            preflight=preflight, env_preflight=env_preflight, root=root)
        try:
            if resume:
                log.emit("resume", run_id=run_id)
                if validate is None:     # a crashed harness cannot time out the containers it started
                    from tools import sandbox as sb
                    try:
                        gone = sb.remove_labeled(cfg["sandbox"], {"argus.run": run_id})
                        log.emit("leftover_containers_removed", count=len(gone))
                    except sb.SandboxUnavailable as e:
                        log.emit("leftover_containers_unchecked", error=str(e)[:200])
                graph.invoke(None, config, durability="sync")
            else:
                log.emit("run_start", run_id=run_id, kind="code_task", contract=str(contract_path))
                graph.invoke({"run_id": run_id, "contract_path": str(contract_path), "tokens_used": 0,
                              "usd_used": 0.0, "elapsed_s": 0.0}, config, durability="sync")
            final = dict(graph.get_state(config).values)
        except EstimateExceeded as e:
            # A model call overspent its reservation (heuristic input counts): the money is spent; stop here.
            # Only the agent node has estimates, and guard raises before committing its result, so the checkpoint
            # still has the attempt pending. Write the terminal status into the checkpoint as the agent's update:
            # routing after it goes to END, so a resume finds the run finished instead of running the attempt again.
            log.emit("budget_violation", source="node", error=str(e))
            old = graph.get_state(config).values.get("status")
            new = st.transition(old, st.FAILED_BUDGET)
            graph.update_state(config, {"status": new, "stop_reason": f"budget_violation: {e}"}, as_node="agent")
            log.emit("status", old=old, new=new, reason=f"budget_violation: {e}")
            final = dict(graph.get_state(config).values)
            if final.get("status") != new or graph.get_state(config).next:
                raise RuntimeError(f"FAILED_BUDGET was not persisted: {final.get('status')}, "
                                   f"next {graph.get_state(config).next}")

    _, totals = reconcile_ledger(log.read())
    result = {k: final.get(k) for k in ("status", "stop_reason", "blocked_reason", "contract_sha", "verdict",
                                        "attempt", "tools", "provenance", "budget_profile", "loop_policy")}
    result["cache"] = cache_totals(log.read(), cfg)
    result.update(run_id=run_id, attempts=len(final.get("failures") or []),
                  usd_billed=totals["usd"], usd_complete=totals["usd_complete"], llm_calls=totals["calls"],
                  llm_calls_unknown=totals["unknown_after_crash"])
    (run_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    log.emit("run_end", **{k: v for k, v in result.items() if k not in ("verdict", "attempt")})
    return result
