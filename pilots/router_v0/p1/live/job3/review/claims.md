# Claims

The agent's structured claims, each with the harness's verdict from its own evidence. A claim the evidence does not support fails acceptance, so a DONE run has none of those.

| # | Claim | Evidence | Verdict | Reason |
|---|---|---|---|---|
| 0 | tests_pass | validation:target | pass |  |
| 1 | issue_fixed | validation:target | pass |  |
| 2 | file_changed | router/job.py | pass |  |
| 3 | file_changed | scripts/argus.py | pass |  |

## Agent's summary

Free text from the agent. It is **not evidence** and nothing in it was checked.

```
Made spent_nano also count stage run ledgers found under runs/ whose id belongs to the job (e.g. a run that started and crashed before job.json recorded it), so `argus list` reports the spend its stage runs recorded; all eight required tests now pass.
```

## Not verified automatically

Recorded when the task was approved. None of these is a passing criterion; a reviewer has to check them.

- that the command is listed in the README or in the module's docstring, and how the usage text reads
- that `argus list` is fast on a large jobs directory (no performance bound is asked nor checked)
- that a jobs directory the user may not read (a permission error on the directory itself) prints anything rather than failing; the issue does not say
