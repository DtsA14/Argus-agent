# Claims

The agent's structured claims, each with the harness's verdict from its own evidence. A claim the evidence does not support fails acceptance, so a DONE run has none of those.

| # | Claim | Evidence | Verdict | Reason |
|---|---|---|---|---|
| 0 | tests_pass | validation:inspectors | pass |  |
| 1 | tests_pass | validation:regression | pass |  |
| 2 | issue_fixed | validation:inspectors | pass |  |
| 3 | file_changed | evals/runlog.py | pass |  |
| 4 | file_changed | scripts/audit_run.py | pass |  |
| 5 | file_changed | scripts/failure_trace.py | pass |  |

## Agent's summary

Free text from the agent. It is **not evidence** and nothing in it was checked.

```
Added evals/runlog.py (read_events, read_result, read_memo, skipped_line) and moved audit_run.py and failure_trace.py onto it. Undecodable event lines are now skipped, with a closing 'events skipped: N' line when N > 0. audit_run.py handles runs with no model call. failure_trace.py reports a directory without result.json and continues.
```

## Not verified automatically

Recorded when the task was approved. None of these is a passing criterion; a reviewer has to check them.

- the other four scripts (analyze_series.py, sim_admission.py, dry_feedback.py, measure_context.py) are protected and untouched; they need Docker or historical data that is not in the snapshot
- that the protected files were left alone: they are protected, but a reviewer must read the diff
- that audit_run.py and failure_trace.py read events, result and memo through evals.runlog (the tests see the output, not the code path)
- readability and the internal layout of evals/runlog.py beyond the four functions the issue names
