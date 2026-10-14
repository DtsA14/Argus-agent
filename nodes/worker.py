from dataset import monthly_totals, product_totals
from harness.errors import TransientError

_seen = set()  # (run_id, task, iteration) already failed once in the "flaky" scenario


def make_worker(gate, usd=0.0):
    """Fake worker (M1). Reports its worst-case usage (tokens and USD) so budgets are exercised for real."""
    def worker(p):
        tid = p["task"]["id"]

        key = (p["run_id"], tid, p["iteration"])
        if p["scenario"] == "flaky" and key not in _seen:
            _seen.add(key)
            raise TransientError(f"{tid}: simulated rate limit")

        rows = gate.call("read_data")

        # Fake "bugs": a real worker would apply the evaluator's feedback instead.
        buggy = p["scenario"] == "never_pass" or (
            p["scenario"] == "fail_then_pass" and tid not in p["fix_ids"]
        )

        if tid == "T1":
            out = {
                "rows": len(rows),
                "months": sorted({r["month"] for r in rows}),
                "products": sorted({r["product"] for r in rows}),
            }
        elif tid == "T2":
            top = sorted(product_totals(rows).items(), key=lambda kv: (-kv[1], kv[0]))[:3]
            if buggy:  # wrong total for the 2nd product
                top = [top[0], (top[1][0], top[1][1] + 300_000), top[2]]
            out = {"top3": [list(x) for x in top]}
        elif tid == "T3":
            trend = sorted(monthly_totals(rows).items())
            if buggy:  # drops one month
                trend = trend[:2] + trend[3:]
            out = {"trend": [list(x) for x in trend]}
        else:
            raise ValueError(f"unknown task {tid}")

        return {"results": {tid: out}, "tokens_used": 2000, "usd_used": usd}

    return worker
