# pr_title2: The title of a review package's pull request draft is cut in the middle of a wor

## Issue

```
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

## What changed

- `M` `codetask/review.py`
- `A` `tests/test_review_pr_title.py` (new test, approved with the task)

## Validation

Every validation was run again in the sandbox on the base commit plus `changes.patch` (see `tests.md`):

- `target`: pass

The task was approved without a reference patch (feasibility: unproven): before this run, no solution had shown that its criteria can be met, and its new tests were drafted, not proven right. Read the tests as well as the change.

## Checks on this package

- ok: `contract_frozen`
- ok: `verdict_passed`
- ok: `summary_bound`
- ok: `input_unchanged`
- ok: `base_commit`
- ok: `changes_in_scope`
- ok: `changes_match_verdict`
- ok: `patch_made`
- ok: `patch_applies`
- ok: `final_state_identical`
- ok: `revalidation_matches`
- ok: `workspace_stable`

## Agent's summary (not evidence)

```
render_pr in codetask/review.py now cuts the issue part of the PR title at a word boundary. It takes the first 81 characters, cuts before the last space and appends "...". A single long word is cut at 80 characters plus "...". A first line of 80 characters or fewer is used unchanged.
```

## How to apply

```sh
git checkout -b <branch> 3b5d26e1fdd662d8421740223f398d978ebd1e59
git apply --whitespace=nowarn changes.patch
```

## Provenance

- base: `https://github.com/DtsA14/Argus-agent.git` at `3b5d26e1fdd662d8421740223f398d978ebd1e59`
- Argus: `b4ba73e272f00ec15bd9daa82f133558fb2d2ac8`
- contract: `pr_title2` sha256 `4de6373c659a82a8a3bddd8fd4dec4dc34abed3e4ce08ea9a788235a47afa7f0`
- models: anthropic:claude-sonnet-5-5; 4 calls, $0.077798
- run: `w2b2a1`, 2 attempt(s); patch sha256 `769e1ec98d6442a3db7d3706116b0987d5ef969a5d0eae229f01a962454315ce`

## Outcome of the pilot

Set by the reviewer, not by Argus: **agent-completed** if the patch is applied unchanged and the independent validation and `verify.sh` pass; **human-assisted** if you change any file in it (keep that change as its own diff); **failed** otherwise. Editing this description is supervision time, not a change of status.
