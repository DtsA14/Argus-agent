"""Phase 3a: stricter programmatic checks on laporan.md, always against ground truth recomputed from the data.

Each case breaks a correct report in one way and asserts the exact set of checks that fail, so a check that
stops firing (or starts firing where it should not) is caught. Before 3a a malformed line was silently skipped
and a repeated month with the same value passed, because the trend was read into a dict."""
import pytest

import dataset
from nodes.evaluator import run_checks

T = dataset.truth()
TOP = [f"- {n}: {v}" for n, v in T["top3"]]
TREND = [f"- {m}: {v}" for m, v in T["trend"]]
RECS = ["1. Bundle Kopi + Teh: together 72% of top-3 revenue.",
        "2. Raise stock ahead of demand: revenue grew 28% from 2026-01 to 2026-06."]


def report(top=TOP, trend=TREND, recs=RECS, pre=("# Laporan Penjualan", ""), extra=()):
    lines = list(pre) + ["## Top 3 Produk", *top, "", "## Tren Bulanan", *trend, "", "## Rekomendasi", *recs]
    return "\n".join(lines + list(extra)) + "\n"


def failing(tmp_path, text):
    p = tmp_path / "laporan.md"
    p.write_text(text, encoding="utf-8")
    checks = run_checks(p, T)
    return {c["id"] for c in checks if not c["ok"]}, {c["id"]: c for c in checks}


def test_a_correct_report_passes_every_check(tmp_path):
    bad, checks = failing(tmp_path, report())
    assert bad == set()
    assert {c["task"] for c in checks.values()} == {"report", "top3", "trend"}


K, Te, R = TOP   # Kopi, Teh, Roti lines
CASES = {
    # structure
    "section repeated": (report(extra=["", "## Top 3 Produk", K]), {"sections"}),
    "section missing": (report().replace("## Rekomendasi\n", "").replace("\n".join(RECS) + "\n", ""),
                        {"sections", "recs_count", "recs_rubric"}),
    "unknown section": (report(extra=["", "## Catatan", "Data lengkap."]), {"sections"}),
    "text before the first section": (report(pre=("# Laporan Penjualan", "Ringkasan singkat.", "")), {"sections"}),
    "title missing": (report(pre=()), {"sections"}),
    # Top 3 Produk
    "top3 line in another format": (report(top=["- Kopi: 4.200.000", Te, R]),
                                    {"top3_format", "top3_count", "top3_names"}),
    "top3 product repeated": (report(top=[K, K, Te, R]), {"top3_count", "top3_no_duplicates", "top3_names"}),
    "top3 not highest first": (report(top=[Te, K, R]), {"top3_order", "top3_names"}),
    "top3 product not in the data": (report(top=[K, Te, f"- Kue: {T['top3'][2][1]}"]),
                                     {"top3_known_products", "top3_names"}),
    "top3 amount wrong": (report(top=[K, f"- Teh: {T['top3'][1][1] + 300_000}", R]), {"top3_amounts"}),
    "top3 only two": (report(top=[K, Te]), {"top3_count", "top3_names"}),
    # Tren Bulanan
    "month repeated with the same value": (report(trend=TREND[:3] + [TREND[2]] + TREND[3:]), {"trend_no_duplicates"}),
    "months newest first": (report(trend=TREND[::-1]), {"trend_order"}),
    "trend line in another format": (report(trend=["- 2026-01: 1,650,000"] + TREND[1:]),
                                     {"trend_format", "trend_months"}),
    "month missing": (report(trend=TREND[:2] + TREND[3:]), {"trend_months"}),
    "month not in the data": (report(trend=TREND + ["- 2026-13: 999999"]), {"trend_no_extra_months"}),
    "month amount wrong": (report(trend=[TREND[0].replace(str(T["trend"][0][1]), "1")] + TREND[1:]),
                           {"trend_amounts"}),
    # Rekomendasi
    "one recommendation": (report(recs=RECS[:1]), {"recs_count", "recs_rubric"}),
    "too many recommendations": (report(recs=[f"{i}. Action {i}: {i}0% more." for i in range(1, 7)]),
                                 {"recs_count"}),
    "recommendation repeated": (report(recs=[RECS[0], "2. " + RECS[0][3:].upper()]), {"recs_no_duplicates"}),
    "numbering skips": (report(recs=[RECS[0], "3. " + RECS[1][3:]]), {"recs_format"}),
    "unnumbered line among recommendations": (report(recs=RECS + ["- also: discount 5%"]), {"recs_format"}),
}


@pytest.mark.parametrize("case", sorted(CASES))
def test_each_defect_fails_exactly_its_checks(tmp_path, case):
    text, expected = CASES[case]
    bad, checks = failing(tmp_path, text)
    assert bad == expected
    for cid in bad:
        assert checks[cid]["detail"], f"{cid} fails without saying why"   # the orchestrator gets the reason


def test_failures_point_at_the_output_to_revise(tmp_path):
    _, checks = failing(tmp_path, report())
    assert all(checks[c]["task"] == "top3" for c in checks if c.startswith("top3_"))
    assert all(checks[c]["task"] == "trend" for c in checks if c.startswith("trend_"))
    assert all(checks[c]["task"] == "report" for c in checks if c.startswith(("recs_", "sections")))


def test_the_synthesized_report_passes(tmp_path):
    # What synthesize writes from correct worker values must pass all checks (no false rejects).
    from harness.events import EventLog
    from nodes.synthesize import make_synthesize
    from tools.registry import ToolGate
    gate = ToolGate("orchestrator", ["write_file"], EventLog(tmp_path / "e.jsonl"))
    results = {"a": {"output": "top3", "value": [list(x) for x in T["top3"]], "iteration": 0},
               "b": {"output": "trend", "value": [list(x) for x in T["trend"]], "iteration": 0}}
    make_synthesize(gate, str(tmp_path), EventLog(tmp_path / "e.jsonl"))({"iteration": 0, "results": results})
    assert {c["id"] for c in run_checks(tmp_path / "laporan.md", T) if not c["ok"]} == set()
