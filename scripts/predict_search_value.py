"""Predicted tokens, cost and status per strategy for the revised search-value design (docs/reviews/TASK_SEARCH_VALUE.md 7.5: 8 step modules
of ~2 KB). Calibration: input tokens ~ 407 + 0.3186 x chars, anchored on live #7 (call 0: 1,790; ListFiles +640).
Prices from config.yaml: Sonnet 5.5 input $2/M, output $10/M. Estimates, not measurements."""
F = lambda kb: 0.3186 * kb * 1000          # noqa: E731  tokens a file adds to every later call
BASE, LISTING, OUT = 1790, 640, 250
ENTRY = F(1.5) + F(0.6) + F(1.2) + F(0.4)  # test, cycle.py, pipeline.py, config/pipeline.json
STEP, OPTS, SEARCH = F(2.0), F(0.7), 150
WRITE = F(1.2) + 600                        # the written file in the reply + two validation results
# (additions after each call, files read, searches)
S = {
    "search_seen":  ([LISTING, ENTRY, SEARCH, STEP + OPTS, WRITE, 0], 6, 1),
    "search_broad": ([LISTING, 900, F(2.5) + F(1.0), ENTRY, SEARCH, STEP + OPTS, WRITE, 0], 8, 2),
    "all_at_once":  ([LISTING, ENTRY, 8 * STEP + OPTS, WRITE, 0], 13, 0),
    "by3_batch2":   ([LISTING, ENTRY, 3 * STEP, 3 * STEP + OPTS, WRITE, 0], 11, 0),
    "by3_last":     ([LISTING, ENTRY, 3 * STEP, 3 * STEP, 2 * STEP + OPTS, WRITE, 0], 13, 0),
}


def attempt(adds, budget):
    """(finished, input tokens, output tokens, calls) of one attempt under the per-call refusal rule."""
    cur, tin, tout = BASE, 0, 0
    for i, a in enumerate(adds):
        if budget - (tin + tout) - cur < OUT:            # output cap below what the reply needs: refused
            return False, tin, tout, i
        tin, tout = tin + cur, tout + OUT
        cur += a + OUT
    return True, tin, tout, len(adds)


def outcome(name, budget):
    adds, files, searches = S[name]
    ok, tin, tout, calls = attempt(adds, budget)
    if not ok:                                           # the same plan again, then stagnant (as simulated)
        tin, tout, calls = 2 * tin, 2 * tout, 2 * calls
    usd = tin * 2 / 1e6 + tout * 10 / 1e6
    return {"status": "DONE" if ok else "FAILED_ACCEPTANCE (2x exhausted)", "tokens": round(tin + tout),
            "usd": round(usd, 3), "calls": calls, "files": files, "searches": searches}


for name in S:
    print(name, "30k:", outcome(name, 30000), "| 60k:", outcome(name, 60000))
print("reservation per attempt (tokens x $10/M): 30k $%.2f, 60k $%.2f" % (30000 * 10e-6, 60000 * 10e-6))
