# Claims

The agent's structured claims, each with the harness's verdict from its own evidence. A claim the evidence does not support fails acceptance, so a DONE run has none of those.

| # | Claim | Evidence | Verdict | Reason |
|---|---|---|---|---|
| 0 | file_changed | models/pricing.py | pass |  |
| 1 | issue_fixed | validation:target | pass |  |
| 2 | tests_pass | validation:regression | pass |  |

## Agent's summary

Free text from the agent. It is **not evidence** and nothing in it was checked.

```
is_peak now handles windows crossing midnight (hour >= start or hour < end), treats start == end as empty, and keeps the UTC conversion and weekdays_only check.
```

## Not verified automatically

Recorded when the task was approved. None of these is a passing criterion; a reviewer has to check them.

- that config.yaml and the other protected files were left alone: they are protected, but a reviewer must read the diff
- that the production peak windows are not affected: none crosses midnight today, so no billed amount changes; the regression nodes and the guard tests show the non-crossing cases unchanged
- readability and the exact form of the condition (the contract fixes the behaviour)
