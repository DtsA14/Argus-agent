# Claims

The agent's structured claims, each with the harness's verdict from its own evidence. A claim the evidence does not support fails acceptance, so a DONE run has none of those.

| # | Claim | Evidence | Verdict | Reason |
|---|---|---|---|---|
| 0 | tests_pass | validation:regression | pass |  |
| 1 | issue_fixed | validation:target | pass |  |
| 2 | file_changed | main.py | pass |  |
| 3 | file_changed | models/registry.py | pass |  |

## Agent's summary

Free text from the agent. It is **not evidence** and nothing in it was checked.

```
main.py now validates --impl before anything runs, with parse_impl_overrides in models/registry.py
```

## Not verified automatically

Recorded when the task was approved. None of these is a passing criterion; a reviewer has to check them.

- a mistyped node under impl: in a config file is ignored too; that is a separate change and is not tested
- the exact wording of the error messages beyond the key words the tests look for
- that graph.py, runner.py and config.yaml were left alone: they are protected, but a reviewer must read the diff
- readability and where the validation lives (the contract fixes the behaviour, not the code layout)
