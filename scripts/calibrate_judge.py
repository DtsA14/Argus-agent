"""Phase 3d: calibrate the rubric judge on reports whose defects are known (docs/MILESTONE3_PLAN.md 3.4).

Every report is judged twice. Scoring rules were fixed before any live run (GPT reviews, 2026-10-15). "Does not
pass" = a valid rejection OR a fail-closed invalid verdict; "valid rejection" = a valid verdict with a failed
criterion. The aggregation deliberately differs by direction (the stricter one each way; see RULES):
  - defective report, semantic detection (threshold): ALL judgements are valid rejections
  - defective report, operational rejection (reported only): ALL judgements do not pass
  - good report, operational false reject (threshold): ANY judgement does not pass
  - good report, semantic false reject (reported only): ANY judgement is a valid rejection
  - a run that stops before every report is judged twice (e.g. the cost cap) is incomplete: no threshold passes
The labels (category, defect, expect_fail) are used for scoring only and never reach the judge.

Costs money only with ARGUS_LIVE=1 and no --fake. The cost cap (calibration.max_usd) is enforced before every
judgement: the next one starts only if what the ledger has billed plus its worst case still fits.

  python scripts/calibrate_judge.py --fake oracle          # dry run: no key, no cost
  ARGUS_LIVE=1 python scripts/calibrate_judge.py           # live, role evaluator (deepseek-flash)
"""
import argparse
import copy
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import dataset  # noqa: E402
from harness.budget import effective_estimates, node_usd_estimates  # noqa: E402
from harness.events import EventLog  # noqa: E402
from harness.llm import LLMCaller, reconcile_ledger  # noqa: E402
from harness.memo import Memo  # noqa: E402
from models.fake import CallableChatModel, reply  # noqa: E402
from models.pricing import is_peak  # noqa: E402
from models.registry import ModelRef  # noqa: E402
from nodes.contract import SALES_REPORT  # noqa: E402
from nodes.facts import build_facts  # noqa: E402
from nodes.judge import make_judge  # noqa: E402
from nodes.synthesize import report_text  # noqa: E402
from runner import load_config  # noqa: E402

FIXTURES = ROOT / "calibration" / "fixtures.json"
STRICT = ("injection", "fabricated")   # categories that must be detected every time
# Written into every calibration.json, so a result explains its own aggregation (GPT review of PR #9).
RULES = {
    "does_not_pass": "a valid verdict with a failed criterion, or an invalid verdict (fail closed)",
    "defect.detected (threshold)": "ALL judgements are valid rejections",
    "defect.rejected_operationally (reported only)": "ALL judgements do not pass",
    "good.false_reject_operational (threshold)": "ANY judgement does not pass",
    "good.false_reject_semantic (reported only)": "ANY judgement is a valid rejection",
    "incomplete": "a report with fewer judgements than required makes the run incomplete; it never passes",
}


def load_fixtures(path=FIXTURES, include_reserve=False):
    data = json.loads(Path(path).read_text(encoding="utf-8"))["fixtures"]
    return [f for f in data if include_reserve or not f.get("reserve")]


def truth_report(recs, truth=None):
    truth = truth or dataset.truth()
    return report_text([list(x) for x in truth["top3"]], [list(x) for x in truth["trend"]], recs)


# ---- scoring (pure; the rules above) -----------------------------------------------------------

def score(results, *, judgements, thresholds):
    """results: [{id, category, judgements: [{valid, passed, failed}]}]. Returns the metrics and the verdict."""
    def complete(r):
        return len(r["judgements"]) == judgements

    def detected(r):          # semantic, defective reports: ALL judgements are valid rejections
        return complete(r) and all(j["valid"] and not j["passed"] for j in r["judgements"])

    def rejected(r):          # operational, defective reports: ALL judgements do not pass
        return complete(r) and all(not j["passed"] for j in r["judgements"])

    defects = [r for r in results if r["category"] != "good"]
    goods = [r for r in results if r["category"] == "good"]
    categories = {}
    for r in defects:
        c = categories.setdefault(r["category"], {"reports": 0, "detected": 0, "rejected_operationally": 0,
                                                  "false_pass_judge_passed": 0, "false_pass_invalid_only": 0})
        c["reports"] += 1
        c["detected"] += detected(r)
        c["rejected_operationally"] += rejected(r)
        if not detected(r):
            if any(j["valid"] and j["passed"] for j in r["judgements"]):
                c["false_pass_judge_passed"] += 1     # the judge let it through at least once
            else:
                c["false_pass_invalid_only"] += 1     # never a valid rejection (invalid or not judged)
    good = {
        "reports": len(goods),
        # good reports: ANY judgement suffices (the stricter aggregation in this direction)
        "false_reject_operational": sum(any(not j["passed"] for j in r["judgements"]) for r in goods),
        "false_reject_semantic": sum(any(j["valid"] and not j["passed"] for j in r["judgements"]) for r in goods),
    }
    all_j = [j for r in results for j in r["judgements"]]
    disagreements = sum(1 for r in results if complete(r) and all(j["valid"] for j in r["judgements"])
                        and len({j["passed"] for j in r["judgements"]}) > 1)
    detection = sum(detected(r) for r in defects) / len(defects) if defects else 0.0
    checks = {
        "detection_rate": {"value": round(detection, 4), "min": thresholds["min_detection_rate"],
                           "ok": detection >= thresholds["min_detection_rate"]},
        **{f"detected_all_{c}": {"value": categories.get(c, {}).get("detected", 0),
                                 "of": categories.get(c, {}).get("reports", 0),
                                 "ok": categories.get(c, {}).get("reports", 0) > 0
                                 and categories[c]["detected"] == categories[c]["reports"]}
           for c in STRICT},
        "false_rejects": {"value": good["false_reject_operational"], "max": thresholds["max_false_rejects"],
                          "ok": good["false_reject_operational"] <= thresholds["max_false_rejects"]},
    }
    incomplete = [r["id"] for r in results if not complete(r)]
    verdict = "incomplete" if incomplete else ("pass" if all(c["ok"] for c in checks.values()) else "fail")
    return {"verdict": verdict, "rules": RULES, "checks": checks, "categories": categories, "good": good,
            "judgements": len(all_j), "invalid_verdicts": sum(not j["valid"] for j in all_j),
            "disagreements": disagreements, "incomplete": incomplete}


# ---- dry-run judges (no key, no cost) ------------------------------------------------------------

def fake_judge(kind, fixtures, truth=None):
    """A judge for --fake runs. 'oracle' rejects exactly the defective reports (looked up by report text, outside
    the prompt), 'pass' passes everything, 'invalid' never calls the tool, 'flaky' alternates oracle and invalid."""
    by_text = {truth_report(f["recs"], truth): f for f in fixtures}
    criteria = [c["id"] for c in SALES_REPORT["rubric"]]
    state = {"n": 0, "seen": {}, "mode": {}}

    def verdict(fx, report):
        quote = report.split("## Rekomendasi\n", 1)[1][:60].split("\n")[0][:40]
        fail = set(fx["expect_fail"]) or ({"grounded"} if fx["category"] != "good" else set())
        items = [{"id": c, "pass": c not in fail, "evidence": [quote], "reason": f"dry-run {kind}"} for c in criteria]
        return reply("", input_tokens=2500, output_tokens=600,
                     tool_calls=[{"name": "SubmitVerdict", "args": {"criteria": items}, "id": f"v{state['n']}"}])

    def respond(messages):
        state["n"] += 1
        text = messages[1].content.split('<report untrusted="true">\n', 1)[1].rsplit("\n</report>", 1)[0]
        fx = by_text[text.replace("<\\/report", "</report")]   # undo the judge prompt's escaping, lookup only
        if len(messages) == 2:                     # a new judgement (a retry has the rejected reply appended)
            n = state["seen"][text] = state["seen"].get(text, 0) + 1
            state["mode"][text] = "invalid" if kind == "invalid" or (kind == "flaky" and n % 2 == 0) else kind
        if state["mode"][text] == "invalid":       # flaky: the 2nd judgement of every report is unusable
            return reply("I approve this report.", input_tokens=2500, output_tokens=20)
        if kind == "pass":
            return verdict({**fx, "category": "good", "expect_fail": []}, text)
        return verdict(fx, text)

    return CallableChatModel(respond=respond)


# ---- reliability guards (DESIGN_503.md options 1 and 2) -------------------------------------------

def _now():
    return datetime.now(timezone.utc)


def consecutive_transient(events):
    """Transient errors in a row at the end of the ledger. Calls refused before sending are skipped: they never
    reached the provider, so they say nothing about whether it is available."""
    n = 0
    for e in reversed([e for e in events if e["event"] == "llm_call" and e.get("status") != "refused"]):
        if e.get("status") != "transient_error":
            break
        n += 1
    return n


# ---- the run ----------------------------------------------------------------------------------

def run(cfg, fixtures, run_dir, *, model=None, log_echo=False):
    ccfg = cfg["calibration"]
    judgements, cap = int(ccfg["judgements"]), float(ccfg["max_usd"])
    cfg = copy.deepcopy(cfg)
    cfg.setdefault("impl", {})["evaluator"] = "llm"
    est_tokens = effective_estimates(cfg)["evaluator"]
    worst_usd = node_usd_estimates(cfg)["evaluator"]           # one judgement, at the peak rate
    log = EventLog(run_dir / "events.jsonl", echo=log_echo)
    judge = make_judge(LLMCaller(cfg, "evaluator", log, model=model), Memo(run_dir / "memo.sqlite"), log,
                       criteria=SALES_REPORT["rubric"], tokens=est_tokens, usd=worst_usd,
                       attempts=int((cfg.get("judge") or {}).get("attempts", 2)))
    truth = dataset.truth()
    facts = build_facts(truth["top3"], truth["trend"])
    log.emit("calibration_start", fixtures=len(fixtures), judgements=judgements, max_usd=cap,
             worst_usd_per_judgement=worst_usd, model=cfg["roles"]["evaluator"]["model"])
    breaker = int((cfg.get("calibration_guard") or {}).get("breaker_consecutive_transient", 0) or 0)
    results, stopped = [], None
    for fx in fixtures:
        entry = {"id": fx["id"], "category": fx["category"], "expect_fail": fx["expect_fail"], "judgements": []}
        results.append(entry)
        for k in range(judgements):
            billed = reconcile_ledger(log.read())[1]["usd"]
            if stopped or billed + worst_usd > cap:            # the next judgement must fit in the cap, worst case
                stopped = stopped or f"cost cap: billed ${billed:.6f} + worst ${worst_usd:.6f} > ${cap:.2f}"
                break
            r = judge(truth_report(fx["recs"], truth), facts, k, task=fx["id"])
            entry["judgements"].append({"valid": r["valid"], "passed": r["passed"], "reason": r["reason"][:200],
                                        "failed": sorted(c for c, v in r["criteria"].items() if not v["pass"])})
            streak = consecutive_transient(log.read())
            if breaker and streak >= breaker:     # the provider is down: stop instead of burning judgements
                stopped = f"provider unavailable: {streak} consecutive transient errors"
                log.emit("calibration_breaker", consecutive=streak, after=fx["id"], judgement=k)
    totals = reconcile_ledger(log.read())[1]
    summary = score(results, judgements=judgements, thresholds=ccfg["thresholds"])
    summary.update(cost_usd=totals["usd"], cost_complete=totals["usd_complete"], llm_calls=totals["calls"],
                   unknown_after_crash=totals["unknown_after_crash"], stopped=stopped, max_usd=cap,
                   model=cfg["roles"]["evaluator"]["model"])
    log.emit("calibration_end", verdict=summary["verdict"], cost_usd=summary["cost_usd"], stopped=stopped)
    out = {"summary": summary, "results": results}
    (run_dir / "calibration.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def print_summary(s):
    print(f"\n== judge calibration: {s['verdict'].upper()}  ({s['model']}, {s['judgements']} judgements, "
          f"${s['cost_usd']:.6f} of ${s['max_usd']:.2f})")
    for name, c in s["checks"].items():
        bound = f">= {c['min']}" if "min" in c else (f"<= {c['max']}" if "max" in c else f"all {c['of']}")
        print(f"  {'ok ' if c['ok'] else 'NO '} {name}: {c['value']} ({bound})")
    print("\n  defective reports: detected = ALL judgements valid rejections; rejected-op = ALL judgements do not pass")
    print("  category              reports  detected  rejected-op  false-pass: judge passed / invalid only")
    for cat, c in sorted(s["categories"].items()):
        print(f"  {cat:<20} {c['reports']:>8} {c['detected']:>9} {c['rejected_operationally']:>12}"
              f"   {c['false_pass_judge_passed']} / {c['false_pass_invalid_only']}")
    g = s["good"]
    print(f"  good reports {g['reports']}: false reject operational (ANY judgement does not pass) "
          f"{g['false_reject_operational']}, semantic (ANY valid rejection) {g['false_reject_semantic']}")
    print(f"  invalid verdicts {s['invalid_verdicts']}, disagreements {s['disagreements']}"
          + (f", stopped: {s['stopped']}" if s["stopped"] else "") + (f", incomplete: {s['incomplete']}" if s["incomplete"] else ""))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fake", choices=["oracle", "pass", "invalid", "flaky"], help="dry run with a fake judge")
    ap.add_argument("--fixtures", default=str(FIXTURES))
    ap.add_argument("--include-reserve", action="store_true")
    ap.add_argument("--run-id", default=time.strftime("calib_%Y%m%d_%H%M%S"))
    ap.add_argument("--runs-dir", default=str(ROOT / "runs"))
    ap.add_argument("--allow-peak", action="store_true",
                    help="start a live run in the judge provider's peak window (skips only the schedule check)")
    a = ap.parse_args(argv)

    cfg = load_config()
    fixtures = load_fixtures(a.fixtures, a.include_reserve)
    model = None
    if a.fake:
        cfg["roles"]["evaluator"]["model"] = "fake:scripted"
        model = fake_judge(a.fake, fixtures)
    else:
        if os.environ.get("ARGUS_LIVE") != "1":
            print("refused: set ARGUS_LIVE=1 for a live calibration (it spends money), or use --fake", file=sys.stderr)
            return 2
        ref = ModelRef.parse(cfg["roles"]["evaluator"]["model"])
        if str(ref) not in cfg["prices"] or cfg["budget"].get("allow_unpriced"):
            print(f"refused: {ref} must be priced and allow_unpriced false", file=sys.stderr)
            return 2
        var = cfg["providers"][ref.provider].get("api_key_env")
        if var and not os.environ.get(var):
            print(f"refused: {var} is not set", file=sys.stderr)
            return 2
        window = (cfg.get("peak_windows") or {}).get(ref.provider)
        if (cfg.get("calibration_guard") or {}).get("refuse_peak") and not a.allow_peak and is_peak(window, _now()):
            print(f"refused: {_now():%a %H:%M} UTC is in {ref.provider}'s peak window {window['utc_hours']} "
                  f"(run #2 met 24 HTTP 503 there); start off-peak or pass --allow-peak", file=sys.stderr)
            return 2
    run_dir = Path(a.runs_dir) / a.run_id
    if run_dir.exists():
        print(f"refused: {run_dir} exists; use a new --run-id", file=sys.stderr)
        return 2
    run_dir.mkdir(parents=True)
    out = run(cfg, fixtures, run_dir, model=model)
    print_summary(out["summary"])
    print(f"\nresults: {run_dir / 'calibration.json'}\nevents:  {run_dir / 'events.jsonl'}")
    return 0 if out["summary"]["verdict"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
