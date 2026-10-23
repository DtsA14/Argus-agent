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
Added the read-only `argus list` command: router/job.py gained list_jobs()/_job_line() (one line per job sorted by job id, spend computed from the stage-run ledgers exactly as status does, '<dir> unreadable' for bad job.json files, 'no jobs' when empty, no lock, no writes) and scripts/argus.py wired the `list` subcommand to it, exiting 0 without config, key, or lock.
```

## Not verified automatically

Recorded when the task was approved. None of these is a passing criterion; a reviewer has to check them.

- No existing test can serve as a regression run in the sandbox: tests/test_router.py is the only test of router/job.py and scripts/argus.py, and every one of its tests builds a git repository through subprocess git, which the sandbox does not have. The new file's test_status_reports_the_same_spend_the_ledgers_record runs in the same validation and pins the status spend figure (money: cap $1.00, spent $0.3750) that `list` must report, so a fix that changes how status counts spend is caught there.
- The default of --jobs-dir (jobs/ inside the Argus checkout) is not exercised: the tests pass --jobs-dir explicitly, because creating jobs/ in the repository under test would be intrusive.
- The process exit status of `python scripts/argus.py list` in a shell is not run (main() is called in-process); the tests do check that main() returns 0.
- What `list` should print for a job.json that is valid JSON but lacks 'state' or 'max_usd', or holds a non-numeric max_usd, is not specified by the issue and is not tested.
- That `argus list --help` documents the command, and that it appears in the module docstring, are not tested.
