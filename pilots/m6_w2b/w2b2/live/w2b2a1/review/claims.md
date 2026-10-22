# Claims

The agent's structured claims, each with the harness's verdict from its own evidence. A claim the evidence does not support fails acceptance, so a DONE run has none of those.

| # | Claim | Evidence | Verdict | Reason |
|---|---|---|---|---|
| 0 | file_changed | codetask/review.py | pass |  |
| 1 | tests_pass | validation:target | pass |  |
| 2 | issue_fixed | validation:target | pass |  |

## Agent's summary

Free text from the agent. It is **not evidence** and nothing in it was checked.

```
render_pr in codetask/review.py now cuts the issue part of the PR title at a word boundary. It takes the first 81 characters, cuts before the last space and appends "...". A single long word is cut at 80 characters plus "...". A first line of 80 characters or fewer is used unchanged.
```

## Not verified automatically

Nothing was recorded.
