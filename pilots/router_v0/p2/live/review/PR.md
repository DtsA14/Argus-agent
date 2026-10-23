# task: argus has no way to see all jobs: status needs a job id the user must already...

## Issue

```
argus has no way to see all jobs: status needs a job id the user must already know.

Add a read-only command `argus list` (scripts/argus.py, with its logic in router/job.py) that prints one line per job
in the jobs directory (--jobs-dir, default jobs/), sorted by job id:

  <job id> <state> spent $<spent with 4 decimals> of $<cap with 2 decimals>

where state and cap come from the job's job.json ("state", "max_usd") and spent is what the job's stage runs have
spent, computed the same way status computes it. Rules:
- only directories that contain a job.json are jobs; any other entry is ignored;
- a job.json that cannot be read or is not valid JSON gives the line "<directory name> unreadable" instead, and the
  other jobs are still listed;
- when the jobs directory does not exist or holds no job, it prints exactly "no jobs";
- it never takes a job's lock and never changes anything; it exits 0.
```

## What changed

- `M` `router/job.py`
- `M` `scripts/argus.py`
- `A` `tests/test_argus_list.py` (new test, approved with the task)

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

## Not verified automatically

- No existing test can serve as a regression run in the sandbox: tests/test_router.py is the only test of router/job.py and scripts/argus.py, and every one of its tests builds a git repository through subprocess git, which the sandbox does not have. The new file's test_status_reports_the_same_spend_the_ledgers_record runs in the same validation and pins the status spend figure (money: cap $1.00, spent $0.3750) that `list` must report, so a fix that changes how status counts spend is caught there.
- The default of --jobs-dir (jobs/ inside the Argus checkout) is not exercised: the tests pass --jobs-dir explicitly, because creating jobs/ in the repository under test would be intrusive.
- The process exit status of `python scripts/argus.py list` in a shell is not run (main() is called in-process); the tests do check that main() returns 0.
- What `list` should print for a job.json that is valid JSON but lacks 'state' or 'max_usd', or holds a non-numeric max_usd, is not specified by the issue and is not tested.
- That `argus list --help` documents the command, and that it appears in the module docstring, are not tested.

## Agent's summary (not evidence)

```
Added the read-only `argus list` command: router/job.py gained list_jobs()/_job_line() (one line per job sorted by job id, spend computed from the stage-run ledgers exactly as status does, '<dir> unreadable' for bad job.json files, 'no jobs' when empty, no lock, no writes) and scripts/argus.py wired the `list` subcommand to it, exiting 0 without config, key, or lock.
```

## How to apply

```sh
git checkout -b <branch> 26befdc1cda45af165e8f26614a3c1e64e20591b
git apply --whitespace=nowarn changes.patch
```

## Provenance

- base: `https://github.com/DtsA14/Argus-agent.git` at `26befdc1cda45af165e8f26614a3c1e64e20591b`
- Argus: `cae50e887e3ce8c7301b517d2ff5c193826b9603`
- contract: `task` sha256 `6ee00c5a1b3377101a51c0fdf9d99ed013ef0df3310d5411c508efa5879921cd`
- models: deepseek:deepseek-flash; 17 calls, $0.021490
- run: `j20261023_062122_c7a4-a1`, 2 attempt(s); patch sha256 `a1dafe0af5ec31a7edf35c308045af9145119ee07fa7f13f16a9f4610f74bd0d`

## Outcome of the pilot

Set by the reviewer, not by Argus: **agent-completed** if the patch is applied unchanged and the independent validation and `verify.sh` pass; **human-assisted** if you change any file in it (keep that change as its own diff); **failed** otherwise. Editing this description is supervision time, not a change of status.
