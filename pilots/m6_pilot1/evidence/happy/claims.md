# Claims

The agent's structured claims, each with the harness's verdict from its own evidence. A claim the evidence does not support fails acceptance, so a DONE run has none of those.

| # | Claim | Evidence | Verdict | Reason |
|---|---|---|---|---|
| 0 | tests_pass | validation:regression | pass |  |
| 1 | issue_fixed | validation:target | pass |  |
| 2 | file_changed | evals/score.py | pass |  |

## Agent's summary

Free text from the agent. It is **not evidence** and nothing in it was checked.

```
run_stats now reads events.jsonl with harness.events.parse_lines, so a line that is not valid JSON is skipped
```

## Not verified automatically

Recorded when the task was approved. None of these is a passing criterion; a reviewer has to check them.

- a line that is valid JSON but not an object (for example 123) is neither required nor tested: harness.events.parse_lines passes it through, and run_stats would then fail on it; that is outside this task
- that independent_checks, honesty, score and aggregate in evals/score.py were left alone: the writable scope is the whole file, so a reviewer must read the diff
- readability of the change
