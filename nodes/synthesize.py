def _recommendations(top3, trend):
    recs = []
    if len(top3) >= 2:
        total = sum(v for _, v in top3)
        share = round(100 * (top3[0][1] + top3[1][1]) / total)
        recs.append(f"Bundle {top3[0][0]} + {top3[1][0]}: together {share}% of top-3 revenue.")
    if len(trend) >= 2:
        recs.append(
            f"Raise stock ahead of demand: total revenue grew from {trend[0][1]} ({trend[0][0]}) "
            f"to {trend[-1][1]} ({trend[-1][0]})."
        )
    return recs


def make_synthesize(gate, report_path, log):
    """Orchestrator role: merge worker results into laporan.md (fake template in milestone 1)."""

    def synthesize(state):
        # Only this iteration's results, looked up by contract output name (task ids are the planner's choice).
        iteration = state.get("iteration", 0)
        by_output = {r["output"]: r.get("value") for r in (state.get("results") or {}).values()
                     if r.get("iteration") == iteration}
        top3 = by_output.get("top3") or []        # a failed worker submits no value
        trend = by_output.get("trend") or []

        lines = ["# Laporan Penjualan", "", "## Top 3 Produk"]
        lines += [f"- {n}: {v}" for n, v in top3]
        lines += ["", "## Tren Bulanan"]
        lines += [f"- {m}: {v}" for m, v in trend]
        lines += ["", "## Rekomendasi"]
        lines += [f"{i}. {r}" for i, r in enumerate(_recommendations(top3, trend), 1)]

        gate.call("write_file", report_path, "\n".join(lines) + "\n")
        return {"tokens_used": 1000}

    return synthesize
