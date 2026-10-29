"""Research stage r1 (docs/reviews/SPEC_RESEARCH_STAGE.md): a model reads a repository and allowlisted documentation and
hands off what the documentation says, with quotes the harness checks. It changes nothing.

  setup     check the issue and the intake, copy the intake snapshot to <run>/source (read-only), freeze the policy:
            the tools, the web config (ReadDocs) and the installed packages of the job's environment
  research  one tool-calling loop: ListFiles, SearchFiles and ReadFile on <run>/source, ReadDocs, then SubmitHandoff.
            The harness gate checks every submit: each source URL was downloaded by ReadDocs in this run, each quote
            is in that page's stored text (whitespace aside, nothing else), the dependency is one installed in the
            environment. Problems go back to the model, at most max_submits submits are checked.
  finalize  write handoff.json and HANDOFF.md, and check that <run>/source is unchanged

The gate does not judge whether the conclusion is right: a human (or Claude, on the fast lane) reviews the handoff
before `argus research-ok` hands it to the drafter.

Same guarantees as the drafter: every model call goes through LLMCaller within one reservation restored from the
ledger, every reply and tool result is committed before the loop moves on (a SubmitHandoff whose result was committed is
never gated again, a ReadDocs page is kept by the run), checkpoints use durability="sync", and every node result is
committed by harness.guard.
"""
import json
import math
import re
import shutil
from pathlib import Path
from typing import List, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from acceptance import contract as ct
from acceptance import intake
from acceptance.workspace import digest, prepare, snapshot
from harness.crash import Crasher
from harness.errors import EstimateExceeded, InputLimitExceeded, LLMCallFailed, ReservationExhausted
from harness.events import EventLog
from harness.guard import guard
from harness.llm import LLMCaller, check_long_context, is_truncated, reconcile_ledger
from harness.memo import Memo
from harness.steps import (call_ids, invalid_call_errors, llm_step_key, message_from_json, message_to_json,
                           reservation_from_ledger, tool_step_key)
from models.registry import ModelRef
from tools import web

from .drafter import FINAL_STEPS, _write, final_from
from .review import fence
from .run import ROOT, RunExists, cache_totals
from .tools import GATED, ListFiles, ReadDocs, ReadFile, SearchFiles, Toolbox

NODE = "research"
SOURCE = "source"
INPUTS = "inputs.json"
MAX_ISSUE = ct.MAX_ISSUE
RUNNING, RESEARCHED, INCONCLUSIVE, NO_HANDOFF = "RUNNING", "RESEARCHED", "INCONCLUSIVE", "NO_HANDOFF"
BLOCKED, FAILED_BUDGET = "BLOCKED", "FAILED_BUDGET"
SUPPORTED, INSUFFICIENT = "SUPPORTED", "INSUFFICIENT_EVIDENCE"
LIMITS = {"problem": 2000, "api_behavior": 3000, "recommended_change": 3000}
QUOTE_MIN, QUOTE_MAX, SOURCES_MAX, UNCERTAINTY_MAX, UNCERTAINTIES_MAX = 20, 600, 5, 1000, 10
STEPS_LEFT_NOTE = ("Harness: {n} steps left of {max}. Submit the handoff soon with SubmitHandoff: a run that ends "
                   "without an accepted handoff has none, whatever was read.")
FINAL_NOTE = "Harness: the last {n} steps. Only SubmitHandoff is offered now; submit what you have."
NUDGE = "Use the tools to research the issue, then call SubmitHandoff."
READ_ONLY = {"scope": {"writable": [], "protected": ["**"]}, "validation": []}
TOOL_VERSIONS = {"ListFiles": "2", "SearchFiles": "2", "ReadFile": "3", "ReadDocs": "1", "SubmitHandoff": "1"}
REQUIREMENT = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;\\]+)")


class Source(BaseModel):
    url: str = Field(description="A page you read with ReadDocs in this run, exactly as you asked for it.")
    quote: str = Field(description=f"{QUOTE_MIN} to {QUOTE_MAX} characters copied exactly from that page.")


class Dependency(BaseModel):
    package: str = Field(description="The package whose API the issue is about, as installed.")
    version: str = Field(description="Its installed version, from the list the harness gave.")


class SubmitHandoff(BaseModel):
    """Submit the research handoff. The harness checks it at once: every url must be a page ReadDocs downloaded in
    this run, every quote must be in that page, and the dependency must be installed at that version."""
    verdict: str = Field(description=f"{SUPPORTED} when the documentation supports the recommended change, "
                                     f"{INSUFFICIENT} when it does not say enough (then say what is missing).")
    problem: str = Field(description="What goes wrong, from the issue and the code.")
    api_behavior: str = Field(description="How the dependency's API behaves, as the quoted documentation says.")
    dependency: Dependency
    sources: List[Source] = Field(description=f"0 to {SOURCES_MAX}; at least 1 for {SUPPORTED}.")
    recommended_change: str = Field("", description="The smallest code change, in words; required for SUPPORTED.")
    uncertainties: List[str] = Field(default_factory=list,
                                     description="What the documentation does not settle, e.g. a page that is not "
                                                 "for the installed version; at least one for INSUFFICIENT_EVIDENCE.")


READ_TOOLS = [ListFiles, SearchFiles, ReadFile, ReadDocs]
# Whatever the config's allowlist says, r1 never gets a tool that writes or runs code (SPEC_RESEARCH_STAGE 4).
READ_ONLY_TOOLS = {GATED[t.__name__] for t in READ_TOOLS}

SYSTEM = "\n".join([
    "You research one issue in a repository against the official documentation of a dependency. You do not fix "
    "anything and you cannot change files: you read the repository and documentation pages, then hand off what the "
    "documentation says.",
    "",
    "Rules:",
    "- Every claim about the dependency's API must rest on a quote from a page you read with ReadDocs in this run, "
    "copied exactly. Never quote from memory: the harness checks every quote against the page it downloaded.",
    "- The installed versions come from the harness (below). Say in uncertainties when a page is not for the "
    "installed version (for example a page of the latest release only).",
    "- When the documentation does not say enough to decide, submit verdict INSUFFICIENT_EVIDENCE with what is "
    "missing. That is a correct result, not a failure; a guess is not.",
    "- Tools: ListFiles, SearchFiles and ReadFile read the repository; ReadDocs reads pages from allowlisted "
    "documentation hosts; SubmitHandoff submits the handoff and is checked at once. Call SubmitHandoff alone in its "
    "reply.",
])


def normalize_name(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def installed_packages(environment, root=ROOT):
    """{normalized name: (name, version)} of an environment's requirements.txt (exact pins only), or None when the
    environment has no such file."""
    path = Path(root) / "environments" / str(environment) / "requirements.txt"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    out = {}
    for line in lines:
        m = REQUIREMENT.match(line.strip())
        if m:
            out[normalize_name(m.group(1))] = (m.group(1), m.group(2))
    return out


def ws(text):
    return " ".join(text.split())


def quoted_in(text, quote):
    """Whether `quote` is in `text` as whole words (both whitespace-normalized by the caller): a quote that starts or
    ends inside a word ("supported" out of "unsupported") is not a quote of the page."""
    i = text.find(quote)
    while i >= 0:
        j = i + len(quote)
        if not (i > 0 and text[i - 1].isalnum() and quote[0].isalnum()) and \
                not (j < len(text) and text[j].isalnum() and quote[-1].isalnum()):
            return True
        i = text.find(quote, i + 1)
    return False


HANDOFF_LABEL = "Reviewed research handoff (r1):"


def issue_with(issue, handoff):
    """The issue the drafter and the agent's contract get after research-ok: the human's issue and the handoff."""
    return f"{issue}\n\n{HANDOFF_LABEL}\n{render(handoff)}"


def _text(args, key, limit, problems, required=True):
    v = args.get(key, "")
    if not isinstance(v, str):
        problems.append(f"{key} must be text")
        return ""
    if required and not v.strip():
        problems.append(f"{key} is empty")
    if len(v) > limit:
        problems.append(f"{key} has {len(v)} characters, more than {limit}")
    return v


def gate(args, *, installed, run_dir, part_chars):
    """(problems, handoff): the problems of a SubmitHandoff (SPEC_RESEARCH_STAGE G1-G5), and when there are none the
    handoff to keep, with each source's page as the run stored it (url, fetched_at, sha256)."""
    problems = []
    if not isinstance(args, dict):
        return ["the arguments must be an object"], None
    verdict = args.get("verdict")
    if verdict not in (SUPPORTED, INSUFFICIENT):
        problems.append(f"verdict must be {SUPPORTED} or {INSUFFICIENT}, not {verdict!r}")
    texts = {k: _text(args, k, n, problems, required=not (k == "recommended_change" and verdict != SUPPORTED))
             for k, n in LIMITS.items()}
    dep = args.get("dependency")
    package = version = None
    if not (isinstance(dep, dict) and isinstance(dep.get("package"), str) and isinstance(dep.get("version"), str)):
        problems.append("dependency must be {package, version}, both text")
    else:
        package, version = dep["package"], dep["version"]
        have = installed.get(normalize_name(package))
        if have is None:
            problems.append(f"G3: {package!r} is not installed in the environment (see the installed list)")
        elif have[1] != version:
            problems.append(f"G3: {have[0]} is installed at {have[1]}, not {version!r}")
    sources = args.get("sources", [])
    kept = []
    if not isinstance(sources, list):
        problems.append("sources must be a list")
        sources = []
    if len(sources) > SOURCES_MAX:
        problems.append(f"sources has {len(sources)} items, more than {SOURCES_MAX}")
    if verdict == SUPPORTED and not sources:
        problems.append(f"{SUPPORTED} needs at least one source")
    for i, s in enumerate(sources[:SOURCES_MAX], 1):
        if not (isinstance(s, dict) and isinstance(s.get("url"), str) and isinstance(s.get("quote"), str)):
            problems.append(f"source {i} must be {{url, quote}}, both text")
            continue
        url, quote = s["url"], ws(s["quote"])
        if not QUOTE_MIN <= len(quote) <= QUOTE_MAX:
            problems.append(f"source {i}: the quote has {len(quote)} characters (without extra whitespace); it must "
                            f"have {QUOTE_MIN} to {QUOTE_MAX}")
            continue
        page = web.stored_page(run_dir, url)
        if page is None:
            problems.append(f"G1 source {i}: {url!r} is not a page ReadDocs downloaded in this run; read it first, "
                            "and give the url exactly as you asked for it")
            continue
        if not any(quoted_in(ws(t), quote) for t in web.served_texts(run_dir, url, part_chars)):
            problems.append(f"G2 source {i}: the quote is not, as whole words, in the parts of {url!r} you read; "
                            "copy it exactly from a part you read")
            continue
        kept.append({"url": url, "quote": quote, "fetched_at": page.get("fetched_at"), "sha256": page.get("sha256"),
                     "final_url": page.get("final_url")})
    unc = args.get("uncertainties", [])
    if not (isinstance(unc, list) and all(isinstance(u, str) and u.strip() for u in unc)):
        problems.append("uncertainties must be a list of non-empty texts")
        unc = []
    elif len(unc) > UNCERTAINTIES_MAX or any(len(u) > UNCERTAINTY_MAX for u in unc):
        problems.append(f"uncertainties: at most {UNCERTAINTIES_MAX} items of at most {UNCERTAINTY_MAX} characters")
    if verdict == INSUFFICIENT and not unc:
        problems.append(f"{INSUFFICIENT} needs at least one uncertainty: what the documentation does not settle")
    if problems:
        return problems, None
    return [], {"verdict": verdict, **texts, "dependency": {"package": package, "version": version},
                "sources": kept, "uncertainties": list(unc)}


def render(handoff):
    """The handoff as text, for the reviewer and for the drafter's issue. Quotes and model text in fences."""
    lines = [f"Verdict: {handoff['verdict']}",
             f"Dependency: {handoff['dependency']['package']}=={handoff['dependency']['version']} (installed)",
             "", "Problem:", fence(handoff["problem"]), "", "Relevant API behavior:", fence(handoff["api_behavior"]),
             "", "Documentation (each quote checked by the harness against the downloaded page):"]
    for s in handoff["sources"]:
        moved = f", redirected to {s['final_url']}" if s.get("final_url") not in (None, s["url"]) else ""
        lines += [f"- {s['url']} (fetched {s['fetched_at']}{moved}, sha256 {str(s['sha256'])[:12]})", fence(s["quote"])]
    if not handoff["sources"]:
        lines.append("- none")
    lines += ["", "Recommended code change:", fence(handoff["recommended_change"] or "(none)"), "", "Uncertainties:"]
    lines += [fence(u) for u in handoff["uncertainties"]] or ["- none"]
    return "\n".join(lines)


def task_prompt(inputs, files, policy):
    pkgs = sorted(policy["installed"].values())
    return "\n".join([
        "Issue (from a human; the problem to research):", inputs["issue"], "",
        f"Repository: intake {inputs['intake']!r}, {files} files, read-only.",
        f"Installed packages of the environment {policy['environment']!r} (from the harness, exact):",
        "  " + ", ".join(f"{n}=={v}" for n, v in pkgs),
        "ReadDocs hosts: " + ", ".join(sorted(policy["web"]["hosts"])) + ".",
        f"SubmitHandoff is checked at most {policy['max_submits']} times; you have {policy['max_steps']} steps."])


def make_researching(caller, memo, log, *, lim, gate_submit, crasher):
    def researching(task_id, toolbox, prompt):
        meta = {"node": NODE, "task": task_id, "iteration": 0}
        res = reservation_from_ledger(log, tokens=lim["attempt_tokens"], usd=lim["attempt_usd"],
                                      max_input=lim["max_input_tokens"], **meta)
        tools = [t for t in READ_TOOLS if GATED[t.__name__] in toolbox.allowed] + [SubmitHandoff]
        submits = 0

        def end(reason, steps, **out):
            log.emit("research_end", reason=reason, steps=steps, submits=submits, **meta)
            return {"end": reason, "steps": steps, "submits": submits, "tokens_used": res.used_tokens,
                    "usd_used": res.used_usd, **out}

        messages = [SystemMessage(SYSTEM), HumanMessage(prompt)]
        for step in range(lim["max_steps"]):
            final = step >= final_from(lim["max_steps"])
            if step > 0 and step == lim["max_steps"] // 2 and not final:
                messages.append(HumanMessage(STEPS_LEFT_NOTE.format(n=lim["max_steps"] - step, max=lim["max_steps"])))
            if step == final_from(lim["max_steps"]):
                messages.append(HumanMessage(FINAL_NOTE.format(n=FINAL_STEPS)))
            step_tools = [SubmitHandoff] if final else tools
            key = llm_step_key(NODE, task_id, 0, step, messages, step_tools, caller.ref)
            cached = memo.get(key)
            if cached is not None:
                msg = message_from_json(cached)
                log.emit("step_replayed", kind="llm", step=step, **meta)
            else:
                try:
                    msg = caller.call(messages, res, tools=step_tools, meta={**meta, "step": step})
                except InputLimitExceeded:
                    return end("context_limit", step)
                except ReservationExhausted:
                    return end("reservation_exhausted", step)
                except LLMCallFailed:
                    return end("llm_failed", step)
                crasher.point("research@after_llm", step=step, **meta)
                memo.put(key, message_to_json(msg))
                log.emit("step_committed", kind="llm", step=step, **meta)
            messages.append(msg)
            if is_truncated(msg):
                log.emit("reply_truncated", step=step, tools=[c.get("name") for c in msg.tool_calls or []], **meta)
                return end("output_truncated", step)
            if invalid_call_errors(msg):
                log.emit("invalid_tool_call", step=step, tools=[c.get("name") for c in msg.invalid_tool_calls], **meta)
                reason = "Rejected: " + "; ".join(invalid_call_errors(msg)) + ". Nothing in this reply was executed."
                messages += [ToolMessage(reason, tool_call_id=i) for i in call_ids(msg, f"call_{step}")]
                continue
            calls = list(msg.tool_calls or [])
            if not calls:
                messages.append(HumanMessage(NUDGE))
                continue
            names = [c.get("name") for c in calls]
            if "SubmitHandoff" in names and len(calls) != 1:
                log.emit("submit_rejected", step=step, tools=names, **meta)
                reason = (f"Rejected: SubmitHandoff must be the only tool call in its reply; this reply had "
                          f"{len(calls)} calls {names}. Nothing in it was executed.")
                messages += [ToolMessage(reason, tool_call_id=c.get("id") or f"call_{step}_{i}")
                             for i, c in enumerate(calls)]
                continue
            for i, c in enumerate(calls):
                name = c.get("name")
                tkey = tool_step_key(NODE, task_id, 0, step, c.get("id"), name, c.get("args"),
                                     TOOL_VERSIONS.get(name, "unknown"), parent=key)
                record = memo.get(tkey)
                if record is not None:
                    log.emit("step_replayed", kind="tool", step=step, tool=name, **meta)
                else:
                    if final and name != "SubmitHandoff":
                        record = {"content": f"Refused: {name} is not offered in the last {FINAL_STEPS} steps; only "
                                             "SubmitHandoff is. Nothing was run.", "finished": False}
                    elif name == "SubmitHandoff":
                        record = gate_submit(c.get("args") or {}, submits + 1)
                    elif name in GATED:
                        record = toolbox.run(c, step_key=tkey)
                    else:
                        record = {"content": f"Unknown tool {name!r}.", "finished": False}
                    crasher.point("research@after_tool", step=step, **meta)
                    crasher.point(f"research@after_tool:{name}", step=step, **meta)
                    memo.put(tkey, record)
                    log.emit("step_committed", kind="tool", step=step, tool=name, **meta)
                if name == "SubmitHandoff":
                    submits += 1
                messages.append(ToolMessage(record["content"], tool_call_id=c.get("id") or f"call_{step}_{i}"))
                if record.get("finished"):
                    return end("submitted", step, handoff=record["handoff"])
                if record.get("exhausted"):
                    return end("submits_exhausted", step)
        return end("max_steps", lim["max_steps"])

    return researching


def make_gate_submit(*, policy, run_dir, log, issue):
    def gate_submit(args, n):
        problems, handoff = gate(args, installed=policy["installed"], run_dir=run_dir,
                                 part_chars=policy["web"]["limits"]["part_chars"])
        if not problems and len(issue_with(issue, handoff)) > MAX_ISSUE:
            problems = [f"the issue with this handoff has {len(issue_with(issue, handoff))} characters, more than "
                        f"{MAX_ISSUE}; shorten the handoff"]
            handoff = None
        log.emit("handoff_checked", submit=n, ok=not problems, problems=problems[:20])
        if not problems:
            return {"content": "Accepted: the handoff passed the harness gate. The research is done.",
                    "finished": True, "handoff": handoff}
        left = policy["max_submits"] - n
        head = f"Rejected ({len(problems)} problem(s)); " + (f"{left} submit(s) left:" if left > 0 else "no submits left:")
        return {"content": "\n".join([head, *[f"- {p}" for p in problems]]), "finished": False, "exhausted": left <= 0}
    return gate_submit


def research_settings(cfg):
    d = cfg["research"]
    ref = ModelRef.parse(cfg["roles"][d["role"]]["model"])
    max_usd = cfg["budget"].get("max_usd")
    max_usd = math.inf if max_usd is None else float(max_usd)
    tokens = min(int(d["attempt_tokens"]), int(cfg["budget"]["max_tokens"]))
    max_input = None if d.get("max_input_tokens") is None else int(d["max_input_tokens"])
    check_long_context(cfg, ref, tokens if max_input is None else max_input, f"research (role {d['role']!r})")
    return {"attempt_tokens": tokens, "attempt_usd": min(float(d["attempt_usd"]), max_usd),
            "max_input_tokens": max_input, "max_steps": int(d["max_steps"]), "max_submits": int(d["max_submits"])}


def with_research_output(cfg):
    """The research role's output cap per model (as the drafter's): the attempt is reserved in USD, so each call's cap
    is still lowered to what fits."""
    d, role = cfg["research"], cfg["research"]["role"]
    model = cfg["roles"][role]["model"]
    by_model = d.get("max_output_tokens_by_model") or {}
    if model not in by_model:
        return cfg
    return {**cfg, "roles": {**cfg["roles"], role: {**cfg["roles"][role], "max_output_tokens": int(by_model[model])}}}


class State(TypedDict, total=False):
    run_id: str
    status: str
    stop_reason: str
    blocked_reason: str
    before: str
    files: int
    policy: dict
    research: dict
    handoff: dict
    source_unchanged: bool
    tokens_used: int
    usd_used: float
    elapsed_s: float


def review_text(run_id, inputs, state, cost):
    h = state.get("handoff")
    return "\n".join([f"# Research handoff: {run_id}", "",
                      f"Status: {state.get('status')} ({state.get('stop_reason')}); cost ${cost['usd']:.4f}", "",
                      "Issue:", fence(inputs["issue"]), "",
                      render(h) if h else "No handoff was accepted.", ""])


def build_graph(cfg, run_dir, log, checkpointer, inputs, *, root, crash_at=None, models=None, web_spawn=None):
    run_dir, root = Path(run_dir), Path(root)
    source = run_dir / SOURCE
    memo = Memo(run_dir / "memo.sqlite")
    crasher = Crasher(crash_at, str(run_dir / ".crashed"), log)
    lim = research_settings(cfg)
    role = cfg["research"]["role"]
    caller = LLMCaller(cfg, role, log, model=(models or {}).get(role))
    common = dict(log=log, retry=cfg["retry"], memo=memo, crash_at=crash_at, crash_marker=str(run_dir / ".crashed"))
    task_id = f"research:{inputs['intake']}"

    def stop(status, reason, blocked=None, **extra):
        log.emit("status", new=status, reason=reason, blocked_reason=blocked)
        return {"status": status, "stop_reason": reason, **({"blocked_reason": blocked} if blocked else {}), **extra}

    def setup(state):
        issue = inputs["issue"]
        if not isinstance(issue, str) or not issue.strip() or len(issue) > MAX_ISSUE:
            return stop(BLOCKED, f"the issue must be non-empty text of at most {MAX_ISSUE} characters", "invalid_input")
        name = inputs["intake"]
        if not isinstance(name, str) or not intake.NAME.match(name):
            return stop(BLOCKED, f"{name!r} is not an intake name", "invalid_input")
        try:
            record = intake.record_for(f"fixtures/repos/{name}", root)
        except intake.IntakeError as e:
            return stop(BLOCKED, str(e), "invalid_input")
        if record is None or record.get("kind", "intake") != "intake":
            return stop(BLOCKED, f"no intake named {name!r}", "invalid_input")
        problems = intake.check(record, root / "fixtures" / "repos" / name)
        if problems:
            return stop(BLOCKED, f"intake {name} changed: " + "; ".join(problems), "invalid_input")
        env = inputs["environment"]
        w = cfg.get("web") or {}
        if env not in (w.get("environments") or []) or not w.get("hosts") or not w.get("limits"):
            return stop(BLOCKED, f"ReadDocs is not allowed for environment {env!r} (web.environments)", "invalid_input")
        installed = installed_packages(env)
        if not installed:
            return stop(BLOCKED, f"environment {env!r} has no requirements.txt of exact pins", "invalid_input")
        if source.exists():
            shutil.rmtree(source)
        try:
            before = prepare(root / "fixtures" / "repos" / name, source)
        except (OSError, ValueError, RuntimeError) as e:
            return stop(BLOCKED, f"the intake could not be copied: {e}", "invalid_input")
        crasher.point("setup@after_copy")
        if lim["attempt_usd"] <= 0:
            return stop(FAILED_BUDGET, "the run cap leaves nothing for the research")
        policy = {"max_steps": lim["max_steps"], "max_submits": lim["max_submits"], "environment": env,
                  "tools": sorted(set((cfg.get("tools") or {}).get(role, [])) & READ_ONLY_TOOLS),
                  "web": {"hosts": dict(w["hosts"]), "limits": dict(w["limits"])},
                  "installed": {k: list(v) for k, v in installed.items()}}
        log.emit("research_policy", **{k: v for k, v in policy.items() if k != "installed"},
                 installed=len(policy["installed"]))
        log.emit("web_granted", hosts=sorted(policy["web"]["hosts"]), limits=policy["web"]["limits"])
        log.emit("status", new=RUNNING, reason=None, blocked_reason=None)
        return {"status": RUNNING, "before": digest(before), "files": len(before), "policy": policy}

    def research(state):
        policy = {**state["policy"], "installed": {k: tuple(v) for k, v in state["policy"]["installed"].items()}}
        docs = web.DocsReader(policy["web"], run_dir, 1, log, **({"spawn": web_spawn} if web_spawn else {}))
        box = Toolbox(str(source), READ_ONLY, {}, policy["tools"], log, crasher=crasher, role=role, docs=docs)
        run = make_researching(caller, memo, log, lim={**lim, "max_steps": policy["max_steps"]},
                               gate_submit=make_gate_submit(policy=policy, run_dir=run_dir, log=log,
                                                             issue=inputs["issue"]), crasher=crasher)
        a = run(task_id, box, task_prompt(inputs, state["files"], policy))
        out = {"research": {"end": a["end"], "steps": a["steps"], "submits": a["submits"]},
               "tokens_used": a["tokens_used"], "usd_used": a["usd_used"]}
        if a["end"] == "submitted":
            h = a["handoff"]
            status = RESEARCHED if h["verdict"] == SUPPORTED else INCONCLUSIVE
            return {**out, **stop(status, f"a handoff passed the gate ({h['verdict']})"), "handoff": h}
        if a["end"] == "llm_failed":
            return {**out, **stop(BLOCKED, "the model provider failed", "provider_failed")}
        return {**out, **stop(NO_HANDOFF, a["end"])}

    def finalize(state):
        unchanged = digest(snapshot(source)) == state["before"]
        out = {"source_unchanged": unchanged}
        if not unchanged:
            out.update(stop(BLOCKED, "the research copy of the intake changed", "source_changed"))
        final = {**state, **out}
        if final.get("handoff") and final["status"] in (RESEARCHED, INCONCLUSIVE):
            _write(run_dir / "handoff.json", json.dumps(final["handoff"], indent=2, ensure_ascii=False) + "\n")
        _, totals = reconcile_ledger(log.read())
        _write(run_dir / "HANDOFF.md", review_text(state.get("run_id"), inputs, final, totals))
        crasher.point("finalize@after_write")
        return out

    g = StateGraph(State)
    g.add_node("setup", guard("setup", setup, **common))
    g.add_node("research", guard("research", research, estimate=lim["attempt_tokens"], usd_estimate=lim["attempt_usd"],
                                 **common))
    g.add_node("finalize", guard("finalize", finalize, **common))
    g.add_edge(START, "setup")
    g.add_conditional_edges("setup", lambda s: "research" if s["status"] == RUNNING else END, ["research", END])
    g.add_edge("research", "finalize")
    g.add_edge("finalize", END)
    return g.compile(checkpointer=checkpointer)


def run_research(*, run_id, runs_dir, cfg, intake_name=None, issue=None, environment=None, max_usd=None, resume=False,
                 crash_at=None, models=None, root=ROOT, echo=False, web_spawn=None):
    """A new run takes the intake, the issue, the job's environment and the run's cap; a resume takes them from
    <run>/inputs.json."""
    run_dir = Path(runs_dir) / run_id
    if not resume and (run_dir / "checkpoints.sqlite").exists():
        raise RunExists(f"run '{run_id}' already exists in {runs_dir}; resume it or pick a new run id")
    if resume and not (run_dir / "checkpoints.sqlite").exists():
        raise RunExists(f"nothing to resume: run '{run_id}' has no checkpoint in {runs_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)
    if resume:
        inputs = json.loads((run_dir / INPUTS).read_text(encoding="utf-8"))
    else:
        if max_usd is None or not float(max_usd) > 0:
            raise ValueError("a research run needs a cap (max_usd > 0)")
        inputs = {"intake": intake_name, "issue": issue, "environment": environment, "max_usd": float(max_usd)}
        _write(run_dir / INPUTS, json.dumps(inputs, indent=2, ensure_ascii=False) + "\n")
    cap = cfg["budget"].get("max_usd")
    cap = inputs["max_usd"] if cap is None else min(float(cap), inputs["max_usd"])
    cfg = with_research_output({**cfg, "budget": {**cfg["budget"], "max_usd": cap}})
    log = EventLog(run_dir / "events.jsonl", echo=echo)
    config = {"configurable": {"thread_id": run_id}, "recursion_limit": 20}
    with SqliteSaver.from_conn_string(str(run_dir / "checkpoints.sqlite")) as cp:
        graph = build_graph(cfg, run_dir, log, cp, inputs, root=root, crash_at=crash_at, models=models,
                            web_spawn=web_spawn)
        try:
            if resume:
                log.emit("resume", run_id=run_id)
                graph.invoke(None, config, durability="sync")
            else:
                log.emit("run_start", run_id=run_id, kind="research", intake=inputs["intake"], max_usd=cap)
                graph.invoke({"run_id": run_id, "tokens_used": 0, "usd_used": 0.0, "elapsed_s": 0.0}, config,
                             durability="sync")
            final = dict(graph.get_state(config).values)
        except EstimateExceeded as e:
            log.emit("budget_violation", source="node", error=str(e))
            graph.update_state(config, {"status": FAILED_BUDGET, "stop_reason": f"budget_violation: {e}"},
                               as_node="finalize")
            final = dict(graph.get_state(config).values)
    _, totals = reconcile_ledger(log.read())
    result = {k: final.get(k) for k in ("status", "stop_reason", "blocked_reason", "research", "source_unchanged")}
    result.update(run_id=run_id, intake=inputs["intake"], max_usd=cap, handoff=bool(final.get("handoff")),
                  verdict=(final.get("handoff") or {}).get("verdict"), cache=cache_totals(log.read(), cfg),
                  usd_billed=totals["usd"], usd_complete=totals["usd_complete"], llm_calls=totals["calls"],
                  llm_calls_unknown=totals["unknown_after_crash"])
    _write(run_dir / "result.json", json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    log.emit("run_end", **result)
    return result
