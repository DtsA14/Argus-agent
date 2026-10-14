import json
import re
from pathlib import Path

import dataset
from harness.budget import next_iteration_blocker
from harness.progress import decide_status, update_progress

from .facts import build_facts, check_numbers, render_line

LINE = re.compile(r"^- (.+?): (\d+)$")
MONTH_LINE = re.compile(r"^- (\d{4}-(?:0[1-9]|1[0-2])): (\d+)$")   # a real YYYY-MM month
REC = re.compile(r"^(\d+)\. (.+)$")
TITLE = "# Laporan Penjualan"
SECTIONS = ("Top 3 Produk", "Tren Bulanan", "Rekomendasi")
MAX_RECS = 5
EVAL_TOKENS = 1500  # fake usage; a real evaluator reports the LLM's usage


def _split(text):
    """(lines before the first section, [(title, lines), ...] in report order)."""
    pre, sections, current = [], [], None
    for line in text.splitlines():
        if line.startswith("## "):
            current = (line[3:].strip(), [])
            sections.append(current)
        else:
            (current[1] if current else pre).append(line)
    return pre, sections


def _body(sections, title):
    """Non-blank lines of the first section with this title (a repeated section fails `sections`)."""
    return next(([l for l in lines if l.strip()] for t, lines in sections if t == title), [])


def _parse(lines, pattern):
    """(parsed matches, lines that do not match). A line in the wrong format is never silently skipped."""
    good, bad = [], []
    for l in lines:
        m = pattern.match(l)
        (good if m else bad).append(m or l)
    return good, bad


def _dupes(items):
    return sorted({x for x in items if items.count(x) > 1})


def _show(lines, n=3):
    return "; ".join(repr(l[:60]) for l in lines[:n]) + (f" (+{len(lines) - n} more)" if len(lines) > n else "")


def _grounded(report_path, lines, truth):
    """(ok, detail): the recommendations in the report are exactly the ones in the provenance, and every number
    in them matches a fact they reference, with facts recomputed from the data (not the workers' values)."""
    prov_path = Path(report_path).with_name("laporan.provenance.json")
    try:
        recs = json.loads(prov_path.read_text(encoding="utf-8"))["recommendations"]
        expected = [render_line(i, r) for i, r in enumerate(recs, 1)]
    except (OSError, ValueError, KeyError, TypeError) as e:
        return False, f"no readable provenance for the recommendations ({type(e).__name__})"
    if lines != expected:
        return False, "the recommendations in the report differ from their provenance"
    facts, problems = build_facts(truth["top3"], truth["trend"]), []
    for i, r in enumerate(recs, 1):
        refs = r.get("facts") or []
        unknown = [x for x in refs if x not in facts]
        if unknown or not refs:
            problems.append(f"recommendation {i}: unknown or missing fact ids {unknown}")
        for where in ("text", "action"):
            problems += [f"recommendation {i} {where}: {e}" for e in check_numbers(r.get(where) or "", facts, refs)]
    return not problems, "; ".join(problems)[:500]


def run_checks(report_path, truth):
    """Programmatic checks against ground truth recomputed from the data, never the agent's own 'done'.
    Every check names the output (task) it concerns, so the orchestrator revises the right worker."""
    checks = []

    def add(cid, task, ok, detail="", kind="code"):
        checks.append({"id": cid, "task": task, "ok": bool(ok), "detail": "" if ok else detail, "kind": kind})

    p = Path(report_path)
    if not p.exists():
        add("report_exists", "report", False, "laporan.md missing")
        return checks
    add("report_exists", "report", True)
    pre, sections = _split(p.read_text(encoding="utf-8"))

    # ---- structure: each required section exactly once, nothing else ----
    titles = [t for t, _ in sections]
    problems = []
    if [l for l in pre if l.strip()] != [TITLE]:
        problems.append(f"before the first section expected only {TITLE!r}, got {_show([l for l in pre if l.strip()])}")
    problems += [f"missing section {s!r}" for s in SECTIONS if s not in titles]
    problems += [f"section {s!r} appears {titles.count(s)} times" for s in _dupes(titles)]
    problems += [f"unknown section {t!r}" for t in titles if t not in SECTIONS]
    add("sections", "report", not problems, "; ".join(problems))

    # ---- Top 3 Produk ----
    top_m, top_bad = _parse(_body(sections, "Top 3 Produk"), LINE)
    top = [(m.group(1), int(m.group(2))) for m in top_m]
    names, amounts = [n for n, _ in top], [v for _, v in top]
    want_names, want_top = [n for n, _ in truth["top3"]], dict(truth["top3"])
    add("top3_format", "top3", not top_bad, f"lines not in the form '- <product>: <integer>': {_show(top_bad)}")
    add("top3_count", "top3", len(top) == 3, f"{len(top)} products listed, expected 3")
    add("top3_no_duplicates", "top3", not _dupes(names), f"listed more than once: {_dupes(names)}")
    unknown = [n for n in names if n not in truth["products"]]
    add("top3_known_products", "top3", not unknown, f"products not in the data: {unknown}")
    add("top3_order", "top3", amounts == sorted(amounts, reverse=True), f"not highest first: {amounts}")
    add("top3_names", "top3", names == want_names, f"report={names} expected={want_names}")
    wrong = [f"{n}: report {v}, recomputed {want_top[n]}" for n, v in top if n in want_top and v != want_top[n]]
    add("top3_amounts", "top3", not wrong, "; ".join(wrong))

    # ---- Tren Bulanan (a list, not a dict: a repeated month must not collapse into one) ----
    tr_m, tr_bad = _parse(_body(sections, "Tren Bulanan"), MONTH_LINE)
    trend = [(m.group(1), int(m.group(2))) for m in tr_m]
    months, want_trend = [m for m, _ in trend], dict(truth["trend"])
    add("trend_format", "trend", not tr_bad, f"lines not in the form '- <YYYY-MM>: <integer>': {_show(tr_bad)}")
    add("trend_no_duplicates", "trend", not _dupes(months), f"months listed more than once: {_dupes(months)}")
    add("trend_order", "trend", months == sorted(months), f"not oldest first: {months}")
    missing = sorted(set(want_trend) - set(months))
    add("trend_months", "trend", not missing, f"missing months: {missing}")
    extra = sorted(set(months) - set(want_trend))
    add("trend_no_extra_months", "trend", not extra, f"months not in the data: {extra}")
    wrong_t = [f"{m}: report {v}, recomputed {want_trend[m]}" for m, v in trend if m in want_trend and v != want_trend[m]]
    add("trend_amounts", "trend", not wrong_t, "; ".join(wrong_t))

    # ---- Rekomendasi ----
    rec_m, rec_bad = _parse(_body(sections, "Rekomendasi"), REC)
    numbers, recs = [int(m.group(1)) for m in rec_m], [m.group(2).strip() for m in rec_m]
    add("recs_format", "report", not rec_bad and numbers == list(range(1, len(numbers) + 1)),
        f"expected items numbered 1., 2., ... with nothing else; numbers {numbers}, other lines {_show(rec_bad)}")
    add("recs_count", "report", 2 <= len(recs) <= MAX_RECS, f"{len(recs)} recommendations, expected 2 to {MAX_RECS}")
    norm = [" ".join(r.lower().split()) for r in recs]
    add("recs_no_duplicates", "report", not _dupes(norm), f"repeated recommendations: {_dupes(norm)}")
    add("recs_grounded", "report", *_grounded(p, [m.group(0) for m in rec_m], truth))
    add("recs_rubric", "report",
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
