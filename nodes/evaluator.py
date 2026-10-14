import re
from pathlib import Path

import dataset
from harness.budget import next_iteration_blocker
from harness.progress import decide_status, update_progress

LINE = re.compile(r"^- (.+?): (\d+)$")
EVAL_TOKENS = 1500  # fake usage; a real evaluator reports the LLM's usage


def _section(text, title):
    out, active = [], False
    for line in text.splitlines():
        if line.startswith("## "):
            active = line[3:].strip() == title
            continue
        if active:
            out.append(line)
    return out


def _pairs(lines):
    return [(m.group(1), int(m.group(2))) for l in lines if (m := LINE.match(l))]


def run_checks(report_path, truth):
    """Programmatic checks against ground truth recomputed from the data, never the agent's own 'done'."""
    checks = []

    def add(cid, task, ok, detail="", kind="code"):
        checks.append({"id": cid, "task": task, "ok": bool(ok), "detail": detail, "kind": kind})

    p = Path(report_path)
    if not p.exists():
        add("report_exists", "REPORT", False, "laporan.md missing")
        return checks
    add("report_exists", "REPORT", True)
    text = p.read_text(encoding="utf-8")

    top = _pairs(_section(text, "Top 3 Produk"))
    want_top = dict(truth["top3"])
    got_names = [n for n, _ in top]
    add("top3_names", "T2", got_names == [n for n, _ in truth["top3"]],
        f"report={got_names} expected={[n for n, _ in truth['top3']]}")
    wrong = [f"{n}: report {v}, recomputed {want_top[n]}" for n, v in top if n in want_top and v != want_top[n]]
    add("top3_amounts", "T2", not wrong and len(top) == 3, "; ".join(wrong))

    got_trend = dict(_pairs(_section(text, "Tren Bulanan")))
    want_trend = dict(truth["trend"])
    missing = sorted(set(want_trend) - set(got_trend))
    add("trend_months", "T3", not missing, f"missing months: {missing}")
    extra = sorted(set(got_trend) - set(want_trend))
    add("trend_no_extra_months", "T3", not extra, f"months not in the data: {extra}")
    wrong_t = [f"{m}: report {v}, recomputed {want_trend[m]}" for m, v in got_trend.items()
               if m in want_trend and v != want_trend[m]]
    add("trend_amounts", "T3", not wrong_t, "; ".join(wrong_t))

    recs = [l for l in _section(text, "Rekomendasi") if re.match(r"^\d+\. ", l)]
    add("recs_rubric", "REPORT",
        len(recs) >= 2 and all(re.search(r"\d", r) for r in recs[:2]),
        "stand-in for the LLM rubric (milestone 3)", kind="rubric-stub")
    return checks


def make_evaluator(report_path, budget, log, iteration_tokens, iteration_usd=0.0):
    def evaluator(state):
        checks = run_checks(report_path, dataset.truth())
        failures = [{"id": c["id"], "task": c["task"], "detail": c["detail"]} for c in checks if not c["ok"]]
        score = round(sum(c["ok"] for c in checks) / len(checks), 3)

        iteration = state.get("iteration", 0) + 1
        best, stale = update_progress(state.get("best_score", -1.0), state.get("stale_rounds", 0), score)
        blocker = next_iteration_blocker(
            budget,
            iteration=iteration,
            tokens_used=state.get("tokens_used", 0) + EVAL_TOKENS,
            elapsed_s=state.get("elapsed_s", 0.0),
            iteration_tokens=iteration_tokens,
            usd_used=state.get("usd_used", 0.0),
            iteration_usd=iteration_usd,
        )
        status, stop_reason = decide_status(
            passed=not failures, budget_blocker=blocker,
            stale_rounds=stale, stagnation_rounds=budget.stagnation_rounds,
        )

        log.emit("eval_verdict", iteration=iteration, score=score, best_score=best, stale_rounds=stale,
                 passed=not failures, failures=[f"{f['task']}:{f['id']}" for f in failures],
                 status=status, stop_reason=stop_reason)
        return {
            "verdict": {"passed": not failures, "score": score, "checks": checks, "failures": failures},
            "iteration": iteration,
            "best_score": best,
            "stale_rounds": stale,
            "status": status,
            "stop_reason": stop_reason,
            "tokens_used": EVAL_TOKENS,
        }

    return evaluator
