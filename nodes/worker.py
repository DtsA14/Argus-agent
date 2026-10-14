from dataset import monthly_totals, product_totals
from harness.errors import TransientError

_seen = set()  # (run_id, task, iteration) already failed once in the "flaky" scenario


def make_worker(gate, usd=0.0):
    """Fake worker (until phase 2c). Works by contract output name, so it follows any plan.

    Reports its worst-case usage (tokens and USD) so budgets are exercised for real.
    Scenarios: a task is "buggy" on never_pass always, and on fail_then_pass until the
    orchestrator attaches feedback to it.
    """

    def worker(p):
        task = p["task"]
        tid, output = task["id"], task["output"]

        key = (p["run_id"], tid, p["iteration"])
        if p["scenario"] == "flaky" and key not in _seen:
            _seen.add(key)
            raise TransientError(f"{tid}: simulated rate limit")

        rows = gate.call("read_data")
        buggy = p["scenario"] == "never_pass" or (p["scenario"] == "fail_then_pass" and not task.get("feedback"))

        if output == "data_check":
            value = {
                "rows": len(rows),
                "months": sorted({r["month"] for r in rows}),
                "products": sorted({r["product"] for r in rows}),
            }
        elif output == "top3":
            top = sorted(product_totals(rows).items(), key=lambda kv: (-kv[1], kv[0]))[:3]
            if buggy:  # wrong total for the 2nd product
                top = [top[0], (top[1][0], top[1][1] + 300_000), top[2]]
            value = [list(x) for x in top]
        elif output == "trend":
            trend = sorted(monthly_totals(rows).items())
            if buggy:  # drops one month
                trend = trend[:2] + trend[3:]
            value = [list(x) for x in trend]
        else:
            raise ValueError(f"fake worker cannot produce output {output!r}")

        result = {"output": output, "value": value, "iteration": p["iteration"]}
        return {"results": {tid: result}, "tokens_used": 2000, "usd_used": usd}

    return worker
