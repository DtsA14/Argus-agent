"""Measure how the code agent's token use grows with the number of files it reads (experiment B, no real model).

  python scripts/measure_context.py calibrate runs/eval_live_4/live_inventory_import ...
  python scripts/measure_context.py simulate

calibrate  Rebuilds the exact messages of every model call of finished live runs from their memo (the rebuild is
           proven exact: each step's recomputed memo key must be found in the memo), counts their characters the way
           the harness does (harness.llm._text plus the tool schemas), and compares with the input tokens Anthropic
           billed. Result: characters per token for this model and this conversation shape.
simulate   Runs the real agent loop (codetask.agent), the real LLMCaller (reservation, refusal before sending) and the
           real tools on synthetic repositories, with a scripted model that follows a reading pattern and a counter
           that uses the calibrated characters per token. Reports, per configuration, the tokens of every call, the
           cumulative total against attempt_tokens, and when and why the attempt ends.

Counts in `simulate` are estimates: they use a ratio calibrated on three live runs, not the provider's tokenizer.
"""
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage  # noqa: E402

from codetask.agent import make_attempt, system_prompt, task_prompt  # noqa: E402
from codetask.tools import Toolbox, offered  # noqa: E402
from harness import llm as hl  # noqa: E402
from harness.events import EventLog  # noqa: E402
from harness.memo import Memo  # noqa: E402
from harness.steps import llm_step_key, message_from_json  # noqa: E402
from runner import load_config  # noqa: E402

TOOL_VERSIONS = {"ListFiles": "1", "ReadFile": "1", "WriteFile": "1", "Finish": "1", "RunValidation": "1:x"}


def chars(messages, tools):
    return sum(len(hl._text(m)) for m in messages) + sum(len(hl._tool_schema_text(t)) for t in (tools or []))


def rebuild(run_dir, cfg):
    """[(step, messages, tools)] for every model call of attempt 0, rebuilt from the memo and proven exact."""
    run_dir = Path(run_dir)
    contract = json.loads((run_dir / "contract.json").read_text())
    tools = offered(cfg["tools"]["coder"])
    ref = hl.ModelRef.parse(cfg["roles"]["coder"]["model"])
    db = sqlite3.connect(run_dir / "memo.sqlite")
    memo = {k: json.loads(v) for k, v in db.execute("select key, value from memo")}
    messages = [SystemMessage(system_prompt(tools)), HumanMessage(task_prompt(contract))]
    out = []
    for step in range(64):
        key = llm_step_key("agent", contract["contract"], 0, step, messages, tools, ref)
        if key not in memo:
            break
        out.append((step, list(messages), tools))
        msg = message_from_json(memo[key])
        messages.append(msg)
        for i, c in enumerate(msg.tool_calls or []):
            tkey = [k for k in memo if k.startswith('["tool", "agent"') and json.loads(k)[4] == step
                    and json.loads(k)[5] == c.get("id")]
            messages.append(ToolMessage(memo[tkey[0]]["content"], tool_call_id=c.get("id") or f"call_{step}_{i}"))
    return out


def calibrate(run_dirs):
    cfg = load_config()
    rows = []
    for d in run_dirs:
        billed = {e["step"]: e["input_tokens"] for e in map(json.loads, (Path(d) / "events.jsonl").read_text()
                                                              .splitlines()) if e["event"] == "llm_call"
                  and e.get("iteration") == 0}
        calls = rebuild(d, cfg)
        assert len(calls) == len(billed), (d, len(calls), len(billed))
        for step, messages, tools in calls:
            rows.append((Path(d).name, step, chars(messages, tools), billed[step]))
    total_c, total_t = sum(r[2] for r in rows), sum(r[3] for r in rows)
    for r in rows:
        print(f"  {r[0]:<24} step {r[1]}  chars {r[2]:>6}  billed input {r[3]:>5}  chars/token {r[2] / r[3]:.2f}")
    ratio = total_c / total_t
    print(f"calls {len(rows)}: chars/token overall {ratio:.3f} "
          f"(min {min(r[2] / r[3] for r in rows):.2f}, max {max(r[2] / r[3] for r in rows):.2f})")
    return ratio


# Fitted on the 20 calls of live runs #2-#6 (calibrate): billed input = A + B x characters; max error 9.4%.
A, B = 407, 0.3186
TOOLS = ["list_files", "read_file", "write_file", "run_validation"]


def estimate(messages, tools):
    return int(A + B * chars(messages, tools))


def module_text(i, size):
    """Plausible Python source of about `size` characters."""
    head = f'"""Module {i}: order handling helpers."""\n'
    body, n = [head], 0
    while sum(map(len, body)) < size:
        body.append(f"\n\ndef helper_{i}_{n}(items, limit=10):\n"
                    "    \"\"\"Return the items whose quantity is below limit, in their original order.\"\"\"\n"
                    "    result = []\n"
                    "    for item in items:\n"
                    "        if item.quantity < limit:\n"
                    "            result.append(item)\n"
                    "    return result\n")
        n += 1
    return "".join(body)[:size]


def scripted(n_files, batch, size):
    """A model that lists the files, reads them `batch` at a time, writes one, validates and finishes. Its reported
    usage is the calibrated estimate of what it was sent and of what it replied."""
    files = [f"src/mod_{i:02d}.py" for i in range(n_files)]
    plan = [[("ListFiles", {})]]
    plan += [[("ReadFile", {"path": f}) for f in files[k:k + batch]] for k in range(0, n_files, batch)]
    plan += [[("WriteFile", {"path": files[0], "content": module_text(0, size) + "\n# fixed\n"})],
             [("RunValidation", {"id": "target"})],
             [("Finish", {"claims": [], "summary": "done"})]]

    def respond(messages):
        step = sum(isinstance(m, AIMessage) for m in messages)
        calls = [{"name": n, "args": a, "id": f"c{step}_{j}"}
                 for j, (n, a) in enumerate(plan[min(step, len(plan) - 1)])]
        out_chars = sum(len(json.dumps(c["args"])) + len(c["name"]) for c in calls)
        return AIMessage(content="", tool_calls=calls, usage_metadata={
            "input_tokens": estimate(messages, offered(TOOLS)), "output_tokens": int(20 + B * out_chars),
            "total_tokens": 0})
    return respond, files


def simulate_one(n_files, batch, size, attempt_tokens=30000, max_steps=12):
    from models.fake import CallableChatModel
    cfg = load_config()
    respond, files = scripted(n_files, batch, size)
    hl.provider_counter = lambda model, margin: (estimate, True)      # calibrated, treated like an exact count
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        ws = tmp / "ws"
        for i, f in enumerate(files):
            (ws / f).parent.mkdir(parents=True, exist_ok=True)
            (ws / f).write_text(module_text(i, size), encoding="utf-8")
        (ws / "tests").mkdir(parents=True, exist_ok=True)
        (ws / "tests" / "test_mod.py").write_text("import unittest\n", encoding="utf-8")
        log = EventLog(tmp / "events.jsonl")
        caller = hl.LLMCaller(cfg, "coder", log, model=CallableChatModel(respond=respond))
        contract = {"contract": "measure", "inputs": {"issue": "Fix the helper."},
                    "scope": {"writable": ["src/**"], "protected": ["tests/**"]},
                    "validation": [{"id": "target"}], "artifacts": [{"schema": "claims_v2"}]}

        def ok(spec, workspace, sandbox_cfg, log=None):
            return {"id": "validation:target", "status": "pass", "reason": "", "evidence": {}}

        box = Toolbox(str(ws), contract, {}, TOOLS, log, validate=ok)
        attempt = make_attempt(caller, Memo(tmp / "memo.sqlite"), log, tokens=attempt_tokens, usd=10.0,
                               max_steps=max_steps, tool_versions=TOOL_VERSIONS)
        end = attempt(contract, box, 0)
        evs = [json.loads(line) for line in (tmp / "events.jsonl").read_text().splitlines()]
    calls = [e for e in evs if e["event"] == "llm_call" and e["status"] == "ok"]
    refused = [e for e in evs if e["event"] == "llm_call" and e["status"] == "refused"]
    read = sum(1 for e in evs if e["event"] == "tool_call" and e.get("tool") == "read_file")
    return {"files": n_files, "batch": batch, "size": size, "end": end["end"], "calls": len(calls),
            "files_read": read, "last_input": calls[-1]["input_tokens"] if calls else 0,
            "total": sum(e["tokens"] for e in calls),
            "per_call": [(e["input_tokens"], e["output_tokens"]) for e in calls],
            "refused_at": refused[0]["est_input"] if refused else None}


def simulate():
    print("estimates: billed input = 407 + 0.3186 x chars (calibrated on 20 live calls, max error 9.4%);"
          " attempt_tokens 30000, max_steps 12")
    print(f"{'size':>5} {'batch':>5} {'files':>5} | {'calls':>5} {'read':>4} {'last in':>7} {'total':>6} | end")
    for size in (1000, 3000):
        for batch in (1, 5, 40):
            for n in (1, 3, 5, 10, 15, 20, 30, 40):
                r = simulate_one(n, batch, size)
                note = f" (refused, est. input {r['refused_at']})" if r["refused_at"] else ""
                print(f"{size:>5} {batch:>5} {n:>5} | {r['calls']:>5} {r['files_read']:>4} {r['last_input']:>7} "
                      f"{r['total']:>6} | {r['end']}{note}")


# ---- SearchFiles scenarios (the real tool in codetask/tools.py; design: docs/reviews/DESIGN_SEARCHFILES.md) ---------

SEARCH_TOOLS = TOOLS + ["search_files"]


def search_repo(ws, n_files, size, symbol="report_key"):
    """n_files modules; the symbol is defined in one and used in another (the two files the fix needs); a third file
    mentions currencies without being part of the bug (a plausible but wrong lead)."""
    files = [f"src/mod_{i:02d}.py" for i in range(n_files)]
    needed = [files[n_files // 3], files[n_files // 2]]
    lead = files[(2 * n_files) // 3]
    for i, f in enumerate(files):
        text = module_text(i, size)
        if f == needed[1]:
            text += f"\n\ndef {symbol}(customer, period, currency):\n    return (customer, period)\n"
        if f == needed[0]:
            text += f"\n\ndef cached(cache, c, p, cur):\n    return cache.get({symbol}(c, p, cur))\n"
        if f == lead:
            text += "\n\nCURRENCIES = ('EUR', 'USD')  # currency formatting table\n"
        (ws / f).parent.mkdir(parents=True, exist_ok=True)
        (ws / f).write_text(text, encoding="utf-8")
    return files, needed, lead


def search_plan(scenario, files, needed, lead, symbol="report_key"):
    """The scripted moves. read_all: no search. perfect: the right term first. wrong_term: a term with no match, then
    the right one. too_common: a term that hits everywhere (cut at 20), then the right one. wrong_lead: a plausible term
    that leads to an unrelated file, which is read, then the right term."""
    search = lambda t: [("SearchFiles", {"text": t})]  # noqa: E731
    read = lambda fs: [("ReadFile", {"path": f}) for f in fs]  # noqa: E731
    if scenario == "read_all":
        steps = [read(files)]
    elif scenario == "perfect":
        steps = [search(symbol), read(needed)]
    elif scenario == "wrong_term":
        steps = [search("cache_key_for"), search(symbol), read(needed)]
    elif scenario == "too_common":
        steps = [search("return"), search(symbol), read(needed)]
    elif scenario == "wrong_lead":
        steps = [search("CURRENCIES"), read([lead]), search(symbol), read(needed)]
    else:
        raise ValueError(scenario)
    return [[("ListFiles", {})]] + steps + [
        [("WriteFile", {"path": needed[-1], "content": module_text(0, 1000) + "\n# fixed\n"})],
        [("RunValidation", {"id": "target"})], [("Finish", {"claims": [], "summary": "done"})]]


def simulate_search_one(n_files, size, scenario, attempt_tokens=30000, max_steps=12):
    from models.fake import CallableChatModel
    cfg = load_config()
    hl.provider_counter = lambda model, margin: (estimate, True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        ws = tmp / "ws"
        files, needed, lead = search_repo(ws, n_files, size)
        (ws / "tests").mkdir(parents=True, exist_ok=True)
        (ws / "tests" / "test_mod.py").write_text("import unittest\n", encoding="utf-8")
        plan = search_plan(scenario, files, needed, lead)

        def respond(messages):
            step = sum(isinstance(m, AIMessage) for m in messages)
            calls = [{"name": n, "args": a, "id": f"c{step}_{j}"}
                     for j, (n, a) in enumerate(plan[min(step, len(plan) - 1)])]
            out_chars = sum(len(json.dumps(c["args"])) + len(c["name"]) for c in calls)
            return AIMessage(content="", tool_calls=calls, usage_metadata={
                "input_tokens": estimate(messages, offered(SEARCH_TOOLS)), "output_tokens": int(20 + B * out_chars),
                "total_tokens": 0})

        log = EventLog(tmp / "events.jsonl")
        caller = hl.LLMCaller(cfg, "coder", log, model=CallableChatModel(respond=respond))
        contract = {"contract": "measure", "inputs": {"issue": "Fix the cache key."},
                    "scope": {"writable": ["src/**"], "protected": ["tests/**"]},
                    "validation": [{"id": "target"}], "artifacts": [{"schema": "claims_v2"}]}

        def ok(spec, workspace, sandbox_cfg, log=None):
            return {"id": "validation:target", "status": "pass", "reason": "", "evidence": {}}

        box = Toolbox(str(ws), contract, {}, SEARCH_TOOLS, log, validate=ok)
        attempt = make_attempt(caller, Memo(tmp / "memo.sqlite"), log, tokens=attempt_tokens, usd=10.0,
                               max_steps=max_steps, tool_versions={**TOOL_VERSIONS, "SearchFiles": "1"})
        end = attempt(contract, box, 0)
        evs = [json.loads(line) for line in (tmp / "events.jsonl").read_text().splitlines()]
    calls = [e for e in evs if e["event"] == "llm_call" and e["status"] == "ok"]
    refused = [e for e in evs if e["event"] == "llm_call" and e["status"] == "refused"]
    count = lambda tool: sum(1 for e in evs if e["event"] == "tool_call" and e.get("tool") == tool)  # noqa: E731
    return {"end": end["end"], "calls": len(calls), "files_read": count("read_file"),
            "searches": count("search_files"), "total": sum(e["tokens"] for e in calls),
            "max_input": max((e["input_tokens"] for e in calls), default=0),
            "refused_at": refused[0]["est_input"] if refused else None}


def simulate_search():
    print("estimates: billed input = 407 + 0.3186 x chars (calibrated, max error 9.4%); attempt_tokens 30000; "
          "the real SearchFiles")
    print(f"{'size':>5} {'files':>5} {'scenario':>11} | {'calls':>5} {'srch':>4} {'read':>4} {'max in':>6} "
          f"{'total':>6} | end")
    for size in (1000, 3000):
        for n in (10, 20, 40, 80):
            for scenario in ("read_all", "perfect", "wrong_term", "too_common", "wrong_lead"):
                r = simulate_search_one(n, size, scenario)
                note = f" (refused, est. input {r['refused_at']})" if r["refused_at"] else ""
                print(f"{size:>5} {n:>5} {scenario:>11} | {r['calls']:>5} {r['searches']:>4} {r['files_read']:>4} "
                      f"{r['max_input']:>6} {r['total']:>6} | {r['end']}{note}")


# ---- the large-repo task shop_coupon_leak: the full run (setup, attempts, acceptance with the real sandbox) -------

SHOP_CONTRACT = ROOT / "fixtures" / "contracts" / "shop_coupon_leak.json"


def shop_plan(condition):
    """Explicit scripted moves. The model does not know `active_rules` up front: it learns it from cart.py."""
    import runpy
    contract = json.loads(SHOP_CONTRACT.read_text(encoding="utf-8"))
    repo = ROOT / contract["inputs"]["workspace"]
    src = sorted(p.relative_to(repo).as_posix() for p in repo.joinpath("src").rglob("*.py")
                 if p.name != "__init__.py")
    fixed = repo.joinpath("src/discounts/registry.py").read_text(encoding="utf-8").replace(
        "    return RULES\n", "    return list(RULES)\n")
    read = lambda fs: [("ReadFile", {"path": f}) for f in fs]  # noqa: E731
    find = lambda t, p="": [("SearchFiles", {"text": t, **({"path": p} if p else {})})]  # noqa: E731
    first = [[("ListFiles", {})]]
    if condition == "no_search_informed":       # reads the directories its names point at, five files per step
        wanted = [f for f in src if f.split("/")[1] in ("checkout", "discounts", "quotes", "pricing")]
        steps = [read(wanted[k:k + 5]) for k in range(0, len(wanted), 5)]
    elif condition == "no_search_naive":        # reads in listing order, five files per step, until the registry
        upto = src[:src.index("src/discounts/registry.py") + 1]
        steps = [read(upto[k:k + 5]) for k in range(0, len(upto), 5)]
    elif condition == "search_effective":
        steps = [find("coupon"), find("coupon", "src/checkout"), read(["src/checkout/cart.py"]),
                 find("def active_rules"), read(["src/discounts/registry.py"])]
    elif condition == "search_ineffective":
        steps = [find("discount"), read(["src/pricing/rounding.py"]), find("coupon", "src/checkout"),
                 read(["src/checkout/cart.py"]), find("def active_rules"), read(["src/discounts/registry.py"])]
    else:
        raise ValueError(condition)
    return first + steps + [[("WriteFile", {"path": "src/discounts/registry.py", "content": fixed})],
                            [("RunValidation", {"id": "target"})],
                            [("Finish", {"claims": [{"claim": "file_changed", "path": "src/discounts/registry.py"},
                                                    {"claim": "issue_fixed", "evidence": "validation:target"}],
                                         "summary": "active_rules now returns a copy."})]]


def shop_one(condition, runs_dir):
    from codetask.run import run_code_task
    from models.fake import CallableChatModel
    cfg = load_config()
    cfg["roles"]["coder"]["model"] = "anthropic:claude-sonnet-5-5"       # priced as the live model would be
    cfg["sandbox"] = {**(cfg.get("sandbox") or {}), "kind": "docker"}
    contract = json.loads(SHOP_CONTRACT.read_text(encoding="utf-8"))
    if condition.startswith("no_search"):
        contract.pop("tools")                                             # the baseline cannot search
    cpath = Path(runs_dir) / f"{condition}.contract.json"
    cpath.parent.mkdir(parents=True, exist_ok=True)
    cpath.write_text(json.dumps(contract), encoding="utf-8")
    plan = shop_plan(condition)
    allowed = cfg["tools"]["coder"] + ct_contract_tools(contract)

    def respond(messages):
        step = sum(isinstance(m, AIMessage) for m in messages)
        calls = [{"name": n, "args": a, "id": f"c{step}_{j}"} for j, (n, a) in enumerate(plan[min(step, len(plan) - 1)])]
        out_chars = sum(len(json.dumps(c["args"])) + len(c["name"]) for c in calls)
        return AIMessage(content="", tool_calls=calls, usage_metadata={
            "input_tokens": estimate(messages, offered(allowed)), "output_tokens": int(20 + B * out_chars),
            "total_tokens": 0})

    hl.provider_counter = lambda model, margin: (estimate, True)
    r = run_code_task(contract_path=cpath, run_id=condition, runs_dir=runs_dir, cfg=cfg,
                      models={"coder": CallableChatModel(respond=respond)})
    evs = [json.loads(line) for line in (Path(runs_dir) / condition / "events.jsonl").read_text().splitlines()]
    count = lambda tool: sum(1 for e in evs if e["event"] == "tool_call" and e.get("tool") == tool)  # noqa: E731
    per_attempt = {}
    for e in evs:
        if e["event"] == "llm_call" and e["status"] == "ok":
            per_attempt[e["iteration"]] = per_attempt.get(e["iteration"], 0) + e["tokens"]
    ends = [e["reason"] for e in evs if e["event"] == "attempt_end"]
    return {"condition": condition, "status": r["status"], "stop": r["stop_reason"], "attempts": r["attempts"],
            "attempt_ends": ends, "tokens_per_attempt": per_attempt, "usd_estimate": round(r["usd_billed"], 4),
            "files_read": count("read_file"), "searches": count("search_files"), "tools": r["tools"]}


def ct_contract_tools(contract):
    from acceptance.contract import contract_tools
    return contract_tools(contract)


def shop():
    print("estimates: billed input = 407 + 0.3186 x chars (calibrated, max error 9.4%), priced as Sonnet 5.5; "
          "attempt_tokens 30000; real sandbox validation and acceptance")
    with tempfile.TemporaryDirectory() as tmp:
        for condition in ("no_search_naive", "no_search_informed", "search_effective", "search_ineffective"):
            print(json.dumps(shop_one(condition, Path(tmp) / "runs")))


if __name__ == "__main__":
    if sys.argv[1] == "shop":
        shop()
    elif sys.argv[1] == "calibrate":
        calibrate(sys.argv[2:])
    elif sys.argv[1] == "simulate":
        simulate()
    elif sys.argv[1] == "search":
        simulate_search()
    elif sys.argv[1] == "detail":
        print(json.dumps(simulate_one(int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])), indent=1))


