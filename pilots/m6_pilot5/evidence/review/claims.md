# Claims

The agent's structured claims, each with the harness's verdict from its own evidence. A claim the evidence does not support fails acceptance, so a DONE run has none of those.

| # | Claim | Evidence | Verdict | Reason |
|---|---|---|---|---|
| 0 | tests_pass | validation:regression | pass |  |
| 1 | issue_fixed | validation:target | pass |  |
| 2 | file_changed | models/pricing.py | pass |  |

## Agent's summary

Free text from the agent. It is **not evidence** and nothing in it was checked.

```
is_peak refuses windows and times it cannot read safely
```

## Not verified automatically

Recorded when the task was approved. None of these is a passing criterion; a reviewer has to check them.

- that config.yaml and the other protected files were left alone: they are protected, but a reviewer must read the diff
- that harness/llm.py refuses before sending when a window is invalid: the code path was read (LLMCaller._output_cap calls multiplier before the request), it is not exercised by these tests
- the exact wording of the messages beyond naming the problem and showing the wrong value
- the behaviour of a falsy window with a naive `now` (the issue says: not checked, False)
