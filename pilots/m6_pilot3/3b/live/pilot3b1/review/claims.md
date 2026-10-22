# Claims

The agent's structured claims, each with the harness's verdict from its own evidence. A claim the evidence does not support fails acceptance, so a DONE run has none of those.

| # | Claim | Evidence | Verdict | Reason |
|---|---|---|---|---|
| 0 | file_changed | scripts/pilot_report.py | pass |  |
| 1 | tests_pass | validation:report | pass |  |
| 2 | tests_pass | validation:regression | pass |  |
| 3 | issue_fixed | validation:report | pass |  |

## Agent's summary

Free text from the agent. It is **not evidence** and nothing in it was checked.

```
Added scripts/pilot_report.py. It reads runs only through evals/runlog.py and cost_is_known. It prints the JSON report in the specified key order and exits 2 with one stderr line on invalid input. No other file changed.
```

## Not verified automatically

Recorded when the task was approved. None of these is a passing criterion; a reviewer has to check them.

- that the script reads runs only through evals.runlog and decides known cost only with cost_is_known (the tests see the output, not the code path)
- that nothing else was changed: the scope protects the rest, but a reviewer must read the diff
- readability and the internal layout of scripts/pilot_report.py
