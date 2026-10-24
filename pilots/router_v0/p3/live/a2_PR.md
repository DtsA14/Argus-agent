# task: scripts/intake_repo.py --check NAME --repo R reports "the snapshot is not the...

## Issue

```
scripts/intake_repo.py --check NAME --repo R reports "the snapshot is not the commit's tree minus the exclusions" for
every task record (fixtures/intake/<task>.json with "kind": "task"), even when the task's repository is exactly the one
that was approved. acceptance/intake.py check_against_repo compares the workspace with the commit's tree only, but a
task's workspace is the commit's tree plus the approved tests, which the record lists:
  - record["added"]: {path: sha256 of the file} for each new test file;
  - record["changed"] (present only when existing tests were changed): {path: {"after": sha256, ...}}.

Fix check_against_repo so that, for a record whose "kind" is "task", the expected snapshot is the commit's tree minus
the exclusions, with each path of "added" set to its hash and each path of "changed" set to its "after" hash. A record
without "kind" or with "kind": "intake" is checked exactly as now.

Every other difference must still be reported, for task records too: a file changed, added or removed beyond the
approved tests, or an approved test whose content differs from its recorded hash. Executable bits are compared as now.
Nothing else changes.
```

## What changed

- `M` `acceptance/intake.py`
- `A` `tests/test_intake_task_snapshot.py` (new test, approved with the task)

## Validation

Every validation was run again in the sandbox on the base commit plus `changes.patch` (see `tests.md`):

- `target`: pass
- `regression`: pass

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

## Not verified automatically

- scripts/intake_repo.py --check NAME --repo R and its output: no test runs the CLI, which needs git and the real repository, neither of which the sandbox has
- that the records already in fixtures/intake/*.json with "kind": "task" now check clean against the Argus repository: that needs git and that repository, so it can only be confirmed by hand with scripts/intake_repo.py
- that a symlink or a special file inside a task's workspace is still reported: the snapshot comparison covers it, but no test of this file builds one (the sandbox is posix-only for that)

## Agent's summary (not evidence)

```
Changed acceptance/intake.py: check_against_repo now builds the expected snapshot of a task record as the commit's tree minus exclusions overlaid with the record's `added` hashes and the `after` hash of each `changed` entry (new `approved_tests` helper); records without a kind or with kind "intake" are still checked against the tree alone, and executable bits are still compared (ignoring only the approved test files' own bits for task records).
```

## How to apply

```sh
git checkout -b <branch> 5d49cf4658f00e8bb81b98494eb73a23fbe7564d
git apply --whitespace=nowarn changes.patch
```

## Provenance

- base: `https://github.com/DtsA14/Argus-agent.git` at `5d49cf4658f00e8bb81b98494eb73a23fbe7564d`
- Argus: `4b27a11da6e841dad9cf43f851073e3c1fed3922`
- contract: `task` sha256 `f90a94c1749d77efb930d2b186c79c4e5207910123af5ef716351a83d9dbab50`
- models: deepseek:deepseek-flash; 6 calls, $0.003929
- run: `j20261024_031449_052d-a2`, 1 attempt(s); patch sha256 `cd13666690e88737b4bf1efd6c54ced234084b22b8abda6207c7997c9ad17657`

## Outcome of the pilot

Set by the reviewer, not by Argus: **agent-completed** if the patch is applied unchanged and the independent validation and `verify.sh` pass; **human-assisted** if you change any file in it (keep that change as its own diff); **failed** otherwise. Editing this description is supervision time, not a change of status.
