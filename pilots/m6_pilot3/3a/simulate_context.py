"""Counterfactual context policies for the live runs pilot3a and pilot3a2: what each attempt would have needed, and
whether it would have fit its 45,000-token reservation, if the harness had sent a smaller context. No model, no
sandbox, no cost: reads events.jsonl (the ledger) and memo.sqlite (replies and tool results) of finished runs.

  python pilots/m6_pilot3/3a/simulate_context.py <runs_root> [--json out.json]

<runs_root> holds pilot3a/ and pilot3a2/.

Method (see CONTEXT_DESIGN.md section 2):
  1. Token rates per kind of content are fitted to the ledger: every step's input minus the previous step's input
     is the previous reply (its output_tokens, exact) plus its tool results (chars x rate of their kind) plus a
     per-call overhead. The fit and its residuals are printed; the baseline then reproduces the ledger exactly
     because each recorded step's residual is carried into every policy (only the removed part is estimated).
  2. A policy rewrites what earlier steps contribute to a later step's input (a stub instead of a stale result,
     a cap on a listing). The trajectory is FORCED: the model is assumed to take the recorded steps whatever its
     context. That is the main assumption; a smaller context can change what the model does.
  3. Attempts that wrote a patch are projected to Finish with the steps the evidence says they still needed: the
     first validation fails with the NameError both runs produced (its real output), one EditFile adds the
     import, a second validation passes, then Finish. Policies that remove the agent's view of the file add a
     ReadFile of audit_run.py before the edit. Projected outputs are assumptions, printed with the results.
  4. Admission follows the harness: a call is refused when est_input + min_output does not fit what is left,
     and max_tokens is min(8192, what is left - est_input).
"""
import json
import sqlite3
import sys
from pathlib import Path

RESERVATION = 45_000
ATTEMPT_USD = 0.45                            # the `large` profile's worst case: 45,000 tokens at the output price
MIN_OUTPUT = 64
MAX_OUTPUT = 8192
PRICE_IN, PRICE_OUT = 2.0, 10.0               # USD per million, solved from the ledger (every ok call matches)
CACHE_READ_X, CACHE_WRITE_X = 0.10, 1.25      # ASSUMPTION: multipliers of the input price; verify before quoting
STUB_TOKENS = 25                              # "[ReadFile scripts/audit_run.py: 4495 chars, sha 1a2b..; elided]"
LIST_CAP_CHARS = 2_000                        # a capped ListFiles: top directories and file counts
READ_CAP_CHARS = 8_000                        # a capped ReadFile (the rest by line range)
KINDS = ["list", "code", "data", "valid", "small"]
FIX_CYCLES = 1                                # --fix-cycles N: EditFile + validation cycles before the passing one
PROJECTED_OUTPUT = {"validate": 150, "read": 120, "edit": 200, "finish": 250}   # ASSUMPTION (recorded small steps: 114-216)


def kind_of(name, args):
    if name == "ListFiles":
        return "list"
    if name == "RunValidation":
        return "valid"
    if name == "ReadFile":
        return "data" if str(args.get("path", "")).endswith("_data.py") else "code"
    return "small"


# ---------------------------------------------------------------- loading

def load_run(run):
    run = Path(run)
    events = [json.loads(line) for line in (run / "events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    calls = {(e["iteration"], e["step"]): e for e in events if e["event"] == "llm_call"}
    replies, results = {}, {}
    db = sqlite3.connect(run / "memo.sqlite")
    for k, v in db.execute("select key, value from memo"):
        key, val = json.loads(k), json.loads(v)
        if key[0] == "llm":
            replies[(key[3], key[4])] = val
        elif key[0] == "tool":
            results[(key[3], key[4], key[5])] = val
    verdicts = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in run.glob("verdict_*.json")}
    return {"name": run.name, "calls": calls, "replies": replies, "results": results, "verdicts": verdicts}


def attempt_steps(run, it):
    """The recorded steps of one attempt: [{step, est_input, status, output, reasoning, calls:[...]}]."""
    steps = []
    for (i, s), c in sorted(run["calls"].items()):
        if i != it:
            continue
        st = {"step": s, "est_input": c["est_input"], "status": c["status"], "output": c.get("output_tokens") or 0,
              "reasoning": c.get("reasoning_tokens") or 0, "calls": []}
        if c["status"] == "ok":
            for tc in run["replies"][(it, s)]["tool_calls"]:
                content = run["results"][(it, s, tc["id"])]["content"]
                st["calls"].append({"name": tc["name"], "path": tc["args"].get("path"), "chars": len(content),
                                    "kind": kind_of(tc["name"], tc["args"])})
        steps.append(st)
    return steps


# ---------------------------------------------------------------- calibration

def solve(a, b):
    """Least squares by the normal equations (stdlib only; the system is small and well conditioned here)."""
    n = len(a[0])
    m = [[sum(r[i] * r[j] for r in a) for j in range(n)] + [sum(r[i] * y for r, y in zip(a, b))] for i in range(n)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(m[r][c]))
        m[c], m[p] = m[p], m[c]
        for r in range(n):
            if r != c and m[c][c]:
                f = m[r][c] / m[c][c]
                m[r] = [x - f * y for x, y in zip(m[r], m[c])]
    return [m[i][n] / m[i][i] for i in range(n)]


def fit_rates(runs):
    rows, ys, seen, labels = [], [], set(), []
    for run in runs:
        for it in sorted({i for i, _ in run["calls"]}):
            steps = attempt_steps(run, it)
            for a, b in zip(steps, steps[1:]):
                if a["status"] != "ok":
                    continue
                x = [sum(c["chars"] for c in a["calls"] if c["kind"] == k) for k in KINDS] + [len(a["calls"])]
                y = b["est_input"] - a["est_input"] - a["output"]
                if (tuple(x), y) in seen:                 # pilot3a2 repeats pilot3a's first steps byte for byte
                    continue
                seen.add((tuple(x), y))
                rows.append(x)
                ys.append(y)
                labels.append((run["name"], it, a["step"], b["est_input"] - a["est_input"], a["output"]))
    coef = solve(rows, ys)
    rates = dict(zip(KINDS + ["per_call"], coef))
    fit = [(lab, lab[3], lab[4] + sum(c * x for c, x in zip(coef, row))) for lab, row in zip(labels, rows)]
    return rates, fit


# ---------------------------------------------------------------- policies

POLICIES = {
    "baseline": {},
    "list_cap": {"list_cap": True},
    "elide_safe": {"elide_safe": True},
    "list_cap+elide_safe": {"list_cap": True, "elide_safe": True},
    "list_cap+read_cap+elide_safe": {"list_cap": True, "read_cap": True, "elide_safe": True},
    "elide_age2": {"elide_age": 2},
    "auto_validate": {"auto_validate": True},
    "list_cap+auto_validate": {"list_cap": True, "auto_validate": True},
}
POLICY_NOTES = {
    "baseline": "the harness as it is",
    "list_cap": f"ListFiles capped at {LIST_CAP_CHARS} chars",
    "elide_safe": "stub: ListFiles after 1 step, a read once its file is written or read again, write/edit "
                  "arguments once the write succeeded, a validation output once a newer one exists",
    "list_cap+elide_safe": "both",
    "list_cap+read_cap+elide_safe": f"plus ReadFile capped at {READ_CAP_CHARS} chars",
    "elide_age2": "every tool result older than 2 steps, write arguments after success (aggressive)",
    "auto_validate": "after a step that writes, the harness runs the validations itself and appends the results "
                     "to that step's tool results; the model never spends a call asking for a validation",
    "list_cap+auto_validate": "both",
}


def result_tokens(call, rates, pol):
    chars = call["chars"]
    if pol.get("list_cap") and call["kind"] == "list":
        chars = min(chars, LIST_CAP_CHARS)
    if pol.get("read_cap") and call["name"] == "ReadFile":
        chars = min(chars, READ_CAP_CHARS)
    return rates[call["kind"]] * chars + rates["per_call"]


def stale(call, j, s, steps, pol):
    """Is the result of `call` (made at step index j) a stub in the input of step index s?"""
    if pol.get("elide_age") is not None:
        if call["kind"] == "valid":
            return any(c["kind"] == "valid" for st in steps[j + 1:s] for c in st["calls"])
        return j < s - pol["elide_age"]
    if not pol.get("elide_safe"):
        return False
    later = [c for st in steps[j + 1:s] for c in st["calls"]]
    if call["kind"] == "list":
        return j < s - 1
    if call["name"] == "ReadFile":
        return any(c["path"] == call["path"] and c["name"] in ("ReadFile", "WriteFile", "EditFile") for c in later)
    if call["kind"] == "valid":
        return any(c["kind"] == "valid" for c in later)
    return False


def write_args_elided(pol):
    return bool(pol.get("elide_safe") or pol.get("elide_age") is not None)


def reply_tokens(st, j, s, pol):
    """What the reply of step index j costs in the input of step index s."""
    writes = [c for c in st["calls"] if c["name"] in ("WriteFile", "EditFile")]
    if writes and write_args_elided(pol) and j < s:
        args = max(st["output"] - st["reasoning"], 0)        # the reply minus its thinking is almost all arguments
        return st["output"] - args + STUB_TOKENS * len(writes)
    return st["output"]


def segments(steps, s, rates, pol):
    """The input of step index s as an ordered list of (segment id, tokens) after the attempt's first prompt."""
    seg = []
    for j in range(s):
        st = steps[j]
        seg.append(((j, "reply", reply_tokens(st, j, s, pol) != st["output"]), reply_tokens(st, j, s, pol)))
        for n, c in enumerate(st["calls"]):
            if stale(c, j, s, steps, pol):
                seg.append(((j, n, "stub"), STUB_TOKENS + rates["per_call"]))
            else:
                seg.append(((j, n, "full"), result_tokens(c, rates, pol)))
    return seg


# ---------------------------------------------------------------- projection

def projected(steps, run_ref, needs_reread, auto_validate=False, cycles=None):
    """The recorded ok steps followed by the steps the evidence says a writing attempt still needed. With
    auto_validate, a validation is not a model call: its result joins the tool results of the writing step."""
    seq = _projected(steps, run_ref, needs_reread, FIX_CYCLES if cycles is None else cycles)
    if not auto_validate:
        return seq
    out = []
    for st in seq:
        if st.get("what") == "validate":
            out[-1] = {**out[-1], "calls": out[-1]["calls"] + st["calls"]}
        else:
            out.append(st)
    for i, st in enumerate(out):
        st["step"] = i
    return out


def _projected(steps, run_ref, needs_reread, cycles=1):
    """`cycles` fix cycles (EditFile, then a validation) after the first failing validation; every validation but
    the last fails with the recorded failing output (CONTEXT_DESIGN.md section 7: the patches needed more than one)."""
    ok = [dict(st) for st in steps if st["status"] == "ok"]
    vfail, vpass = run_ref["valid_fail_chars"], run_ref["valid_pass_chars"]
    tail = [("validate", [{"name": "RunValidation", "path": None, "chars": vfail, "kind": "valid"}])]
    if needs_reread:
        tail.append(("read", [{"name": "ReadFile", "path": "scripts/audit_run.py", "chars": run_ref["audit_chars"], "kind": "code"}]))
    for i in range(cycles):
        tail += [("edit", [{"name": "EditFile", "path": "scripts/audit_run.py", "chars": 96, "kind": "small"}]),
                 ("validate", [{"name": "RunValidation", "path": None,
                                "chars": vpass if i == cycles - 1 else vfail, "kind": "valid"}])]
    tail += [("finish", [])]
    for what, calls in tail:
        ok.append({"step": len(ok), "est_input": None, "status": "projected", "output": PROJECTED_OUTPUT[what],
                   "reasoning": 0, "calls": calls, "what": what})
    return ok


def simulate(steps, base, resid, rates, pol, reservation=RESERVATION, usd_limit=None, billed_cached=False):
    """Run the attempt's calls through the reservation (None: no token limit). With usd_limit, the attempt is also
    held to that many USD the way a per-call USD admission would do it: before each call, the exact input at the
    input price plus max_tokens at the output price must fit what is left (worst case: no cache hits); what is
    then spent is the real price, with cache reads when billed_cached. Returns per-call rows and the outcome."""
    reservation = reservation if reservation is not None else 10 ** 12
    used, rows, prev_seg, usd, usd_cached = 0, [], None, 0.0, 0.0
    for s, st in enumerate(steps):
        seg = segments(steps, s, rates, pol)
        r = resid[s] if s < len(resid) else resid[-1]
        est = round(base + sum(t for _, t in seg) + r)
        left = reservation - used
        cap = min(MAX_OUTPUT, left - est)
        bound = "reservation_exhausted"
        if usd_limit is not None:
            spent = usd_cached if billed_cached else usd
            usd_cap = int((usd_limit - spent - est * PRICE_IN / 1e6) / (PRICE_OUT / 1e6))
            if usd_cap < cap:
                cap, bound = usd_cap, "usd_exhausted"
        if cap < MIN_OUTPUT:
            rows.append({"step": s, "est_input": est, "left": left, "status": "refused"})
            return rows, {"end": bound, "at_step": s, "used": used, "usd": usd, "usd_cached": usd_cached}
        if st["output"] > cap:
            rows.append({"step": s, "est_input": est, "left": left, "status": "truncated"})
            return rows, {"end": "output_truncated", "at_step": s, "used": used, "usd": usd, "usd_cached": usd_cached}
        # prompt caching: the prefix shared with the previous call is read from cache, the rest is written
        if prev_seg is None:
            cached = 0
        else:
            cached = base
            for a, b in zip(prev_seg, seg):
                if a != b:
                    break
                cached += a[1]
        cached = min(cached, est)
        used += est + st["output"]
        usd += (est * PRICE_IN + st["output"] * PRICE_OUT) / 1e6
        usd_cached += (cached * PRICE_IN * CACHE_READ_X + (est - cached) * PRICE_IN * CACHE_WRITE_X
                       + st["output"] * PRICE_OUT) / 1e6
        rows.append({"step": s, "est_input": est, "left": left, "status": st["status"], "output": st["output"],
                     "what": st.get("what") or ",".join(c["name"] for c in st["calls"])})
        prev_seg = seg
    return rows, {"end": "finished" if steps and steps[-1].get("what") == "finish" else "recorded_steps_done",
                  "at_step": len(steps), "used": used, "usd": usd, "usd_cached": usd_cached}


def residuals(steps, rates):
    """Ledger input minus the baseline estimate, per recorded step (ok and refused): carried into every policy."""
    base = steps[0]["est_input"]
    out = []
    for s, st in enumerate(steps):
        if st["est_input"] is None:
            break
        out.append(st["est_input"] - (base + sum(t for _, t in segments(steps, s, rates, {}))))
    return base, out


# ---------------------------------------------------------------- report

def main():
    global FIX_CYCLES
    root = Path(sys.argv[1])
    out_json = sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None
    if "--fix-cycles" in sys.argv:
        FIX_CYCLES = int(sys.argv[sys.argv.index("--fix-cycles") + 1])
        if FIX_CYCLES < 1:
            sys.exit("--fix-cycles must be at least 1")
    if FIX_CYCLES != 1:                       # the default output stays byte-identical to evidence/context_sim/
        print(f"== fix cycles projected after the first failing validation: {FIX_CYCLES}")
    runs = {n: load_run(root / n) for n in ("pilot3a", "pilot3a2")}
    rates, fit = fit_rates(runs.values())

    # the baseline must give back every recorded est_input exactly, or nothing below means anything
    checked = 0
    for run in runs.values():
        for it in sorted({i for i, _ in run["calls"]}):
            steps = attempt_steps(run, it)
            base, resid = residuals(steps, rates)
            seq = [dict(st, output=st["output"] or 1) for st in steps]
            rows, _ = simulate(seq, base, resid, rates, {}, reservation=None)
            got = [x["est_input"] for x in rows]
            want = [st["est_input"] for st in steps]
            if got != want:
                sys.exit(f"baseline does not reproduce the ledger for {run['name']} attempt {it}: {got} != {want}")
            checked += len(want)
    print(f"== 0. baseline reproduces every recorded est_input of both runs ({checked} calls, ok and refused): yes")

    p3a = runs["pilot3a"]
    vfail = next(c for c in attempt_steps(p3a, 1)[0]["calls"] if c["kind"] == "valid")["chars"]
    reg = next(c for c in p3a["verdicts"]["verdict_0"]["criteria"] if c["id"] == "validation:regression")
    vpass = len(reg["evidence"].get("output_tail") or "")
    audit = next(c for c in attempt_steps(p3a, 1)[0]["calls"] if c["path"] == "scripts/audit_run.py")["chars"]
    ref = {"valid_fail_chars": vfail, "valid_pass_chars": vpass, "audit_chars": audit}

    print("== 1. token rates fitted to the ledger (tokens per character; per_call in tokens)")
    print("   " + ", ".join(f"{k} {v:.4f}" if k != "per_call" else f"{k} {v:.1f}" for k, v in rates.items()))
    worst = max(abs(p - d) for _, d, p in fit)
    for (name, it, s, d, _), _, p in fit:
        print(f"   {name:<9} it{it} s{s}->s{s + 1}  ledger +{d:>6}  fit +{p:>8.0f}  error {p - d:+5.0f}")
    print(f"   largest error {worst:.0f} tokens; {len(fit)} distinct transitions for {len(rates)} parameters "
          "(near-exact by construction: read the sensitivity rows, not the fit)")
    print(f"   projection inputs: failing validation {vfail} chars (pilot3a it1 s0, the real output on attempt 0's "
          f"workspace); passing validation {vpass} chars (regression output_tail); audit_run.py {audit} chars")
    print(f"   projected outputs (assumed): {PROJECTED_OUTPUT}; cache multipliers (assumed): read x{CACHE_READ_X}, "
          f"write x{CACHE_WRITE_X}")

    # cross-check with INVESTIGATION.md section 3 (≈ 98-99k for the recorded steps + one validation + Finish)
    st_a = attempt_steps(p3a, 0)
    seq = [s for s in _projected(st_a, ref, False, 1) if s.get("what") not in ("edit",)]
    seq = seq[:4] + [s for s in seq if s.get("what") == "finish"]
    b, res = residuals(st_a, rates)
    chk = simulate(seq, b, res, rates, {}, reservation=None)[1]["used"]
    print(f"   cross-check: pilot3a attempt 0 + one validation + Finish = {chk} tokens "
          "(INVESTIGATION.md section 3: about 98-99 thousand)")

    writers = [("A", "pilot3a", 0, "wrote 1 file + 4 edits at s2; NameError left"),
               ("B", "pilot3a2", 1, "wrote 1 file + 1 edit at s2; same NameError")]
    explorers = [("C", "pilot3a", 1, "explored after seeing the NameError; never edited"),
                 ("D", "pilot3a2", 0, "searched at s2; never wrote")]
    report = {"rates": rates, "fit_max_error": worst, "projection": ref, "writers": [], "explorers": []}

    print()
    print("== 2. writer attempts projected to Finish: what each policy needs, and where 45,000 tokens stops it")
    print(f"   {'policy':<29} {'calls':>5} {'needs':>7} {'x45k':>5} {'peak in':>7} {'USD':>7} {'USD cached':>10}"
          f"  {'first 3 calls':>13}  with the 45,000 reservation")
    for label, run_name, it, note in writers:
        steps = attempt_steps(runs[run_name], it)
        print(f"-- {label}: {run_name} attempt {it} ({note})")
        for pname, pol in POLICIES.items():
            seq = projected(steps, ref, needs_reread=write_args_elided(pol), auto_validate=pol.get("auto_validate", False))
            base, resid = residuals(steps, rates)
            free_rows, free = simulate(seq, base, resid, rates, pol, reservation=None)
            rows, o = simulate(seq, base, resid, rates, pol)
            u_rows, u = simulate(seq, base, resid, rates, pol, reservation=None, usd_limit=ATTEMPT_USD)
            first3 = sum(x["est_input"] + x["output"] for x in free_rows[:3])
            if o["end"] == "finished":
                lim = f"finishes, {RESERVATION - o['used']} left"
            else:
                lim = f"refused at call {o['at_step']} ({rows[-1]['est_input']} in, {rows[-1]['left']} left)"
            ulim = (f"finishes at ${u['usd']:.4f}" if u["end"] == "finished"
                    else f"stops at call {u['at_step']} ({u['end']})")
            if FIX_CYCLES != 1:
                _, uc = simulate(seq, base, resid, rates, pol, reservation=None, usd_limit=ATTEMPT_USD, billed_cached=True)
                ulim += "; billed with cache: " + (f"finishes at ${uc['usd_cached']:.4f}" if uc["end"] == "finished"
                                                   else f"stops at call {uc['at_step']} ({uc['end']})")
            print(f"   {pname:<29} {len(seq):>5} {free['used']:>7} {free['used'] / RESERVATION:>5.2f} "
                  f"{max(x['est_input'] for x in free_rows):>7} {free['usd']:>7.4f} {free['usd_cached']:>10.4f}"
                  f"  {first3:>13}  {lim:<44} USD-only ${ATTEMPT_USD}: {ulim}")
            sens = {}
            for scale in (0.85, 1.15):
                r = {k: (v * scale if k != "per_call" else v) for k, v in rates.items()}
                b2, res2 = residuals(steps, r)
                sens[scale] = simulate(seq, b2, res2, r, pol, reservation=None)[1]["used"]
            report["writers"].append({"case": label, "run": run_name, "attempt": it, "policy": pname,
                                      "calls": len(seq), "needs": free["used"], "usd": free["usd"],
                                      "usd_cached": free["usd_cached"], "first3": first3,
                                      "with_reservation": o, "with_usd_only": u, "needs_at_rates_x0.85": sens[0.85],
                                      "needs_at_rates_x1.15": sens[1.15], "rows": free_rows})

    print()
    print("== 3. sensitivity of 'needs' to the fitted rates (only the removed part is estimated)")
    for w in report["writers"]:
        print(f"   {w['case']} {w['policy']:<29} x0.85 {w['needs_at_rates_x0.85']:>7}   fit {w['needs']:>7}   "
              f"x1.15 {w['needs_at_rates_x1.15']:>7}")

    if FIX_CYCLES != 1:                       # printed only with --fix-cycles, so the default output stays as it was
        print()
        print(f"== 3b. USD admission (${ATTEMPT_USD} per attempt, no cache) at rates x0.85 / fit / x1.15: "
              "fin = finishes, STOP = refused before Finish; USD spent")
        for label, run_name, it, _ in writers:
            steps = attempt_steps(runs[run_name], it)
            for pname, pol in POLICIES.items():
                seq = projected(steps, ref, needs_reread=write_args_elided(pol), auto_validate=pol.get("auto_validate", False))
                outs = []
                for scale in (0.85, 1.0, 1.15):
                    r = {k: (v * scale if k != "per_call" else v) for k, v in rates.items()}
                    b2, res2 = residuals(steps, r)
                    u2 = simulate(seq, b2, res2, r, pol, reservation=None, usd_limit=ATTEMPT_USD)[1]
                    outs.append(f"{'fin ' if u2['end'] == 'finished' else 'STOP'} ${u2['usd']:.4f}")
                print(f"   {label} {pname:<29} " + " | ".join(outs))

    print()
    print("== 4. explorer attempts: the recorded steps (and the refused one) under each policy, 45,000 reservation")
    for label, run_name, it, note in explorers:
        steps = attempt_steps(runs[run_name], it)
        base, resid = residuals(steps, rates)
        print(f"-- {label}: {run_name} attempt {it} ({note}); {len(steps)} calls recorded, the last refused")
        for pname, pol in POLICIES.items():
            seq = [dict(st) for st in steps]
            seq[-1]["output"] = seq[-1]["output"] or PROJECTED_OUTPUT["validate"]
            rows, o = simulate(seq, base, resid, rates, pol)
            lim = (f"all {len(seq)} admitted, {RESERVATION - o['used']} left" if o["end"] == "recorded_steps_done"
                   else f"refused at call {o['at_step']} ({rows[-1]['est_input']} in, {rows[-1]['left']} left)")
            print(f"   {pname:<29} {lim}")
            report["explorers"].append({"case": label, "run": run_name, "attempt": it, "policy": pname, "outcome": o})

    print()
    print("Policies:")
    for k, v in POLICY_NOTES.items():
        print(f"   {k:<29} {v}")
    if out_json:
        Path(out_json).write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
