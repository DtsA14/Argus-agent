# Draft review: `argus_p7` (w2b2d2)

Status: **NO_DRAFT** (submits_exhausted)

Written by the harness from the draft and its check. The draft itself was written by a model: read the tests. A passing baseline shows only that the new tests fail now, not that they test the right thing.

## Issue

```text
The title of a review package's pull request draft is cut in the middle of a word.

codetask/review.py, render_pr: the first line of review/PR.md is "# " followed by the contract name, ": " and the first
line of the task's issue cut to its first 80 characters. A long first line therefore ends mid-word, for example
"fix_x: The title of a review package's pull request draft is cut in the middle of a wor".

Wanted, for the issue part of the title only (call the issue's stripped first line L):
- if L has at most 80 characters, it is used as it is, with nothing added;
- otherwise take L's first 81 characters and cut them just before their last space; if that leaves something, remove
  trailing spaces and append "..." (three dots, no space before them);
- if those 81 characters contain no space (one long word), or the cut leaves nothing, use L's first 80 characters
  followed by "...".

Everything else stays as it is: the contract name and ": " before it, the cleaning of the whole heading for the
Markdown table cell (the existing cell(title, 120)), the rest of PR.md, and every other file of the review package.
```

No draft passed its check; nothing to approve.

## Cost

Drafter: $0.1874, 7 model calls, 4 submits, 6 steps (ended: submits_exhausted).
