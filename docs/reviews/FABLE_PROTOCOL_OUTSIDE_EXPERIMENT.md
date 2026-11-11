> Verbatim copy of Fable's `PROTOCOL_OUTSIDE_EXPERIMENT.md` (session B2), pasted by Atha on 2026-11-11 and not edited, apart from this note.
> **Proposal, not approved.** Fable's covering message: the ten issues are not currently open ones but issues closed by a merged pull request, given to Argus at
> the fix's parent commit (so they are open at the commit Argus sees and the maintainer's tests exist for grading with `scripts/swe_grade.py`); all three candidates
> are UNVERIFIED (web search confirmed only licences and that packagers test them with pytest); the kill and success lines were computed with a binomial model;
> each repository needs its own sandbox environment built and checked first (a config change Fable did not look into); the review notes, `Reconciliation.md` and
> `SPEC_JUDGE.md` were not re-read. Claude's checks (probabilities, candidate activity, issue counts) are in section 11 of
> [`FABLE_REVIEW_2026-11-11.md`](FABLE_REVIEW_2026-11-11.md).

# Protocol: Argus on issues it did not shape (outside experiment v0)

Status: proposal (Fable, 2026-11-11), for Atha's "ok". CLI and caps checked at 3d3b078. Nothing was run.

## 1. Question

How often does Argus turn a real issue, verbatim, into a patch a maintainer could merge, unaided, and at what cost?

## 2. Repositories

Criteria, all required:
- Pure Python, permissive licence, not one of SWE-bench's 12 repositories.
- pytest suite that runs offline in under 120 s in the sandbox (512 MB, 1 CPU).
- At most 30,000 lines; dependencies installable into one pinned image.
- No symlinks or submodules (the intake refuses them), or removable with `--exclude`.
- At least 10 issues closed by a merged pull request in the last 12 months, written by users.

Candidates (web search only; none cloned or inspected):

| Repository | Confirmed | Status |
|---|---|---|
| `python-humanize/humanize` | MIT; packagers test it with pytest; pushed May 2026 | UNVERIFIED: suite time, issue count, size |
| `tkem/cachetools` | MIT; a packager tests it with pytest | UNVERIFIED: activity, issue count, suite time |
| `mahmoud/boltons` | BSD; pure Python, no dependencies; pytest | UNVERIFIED: recent activity (last push seen: Feb 2025) |

A candidate that fails a criterion is replaced before selection.

## 3. Issue selection (no cherry-picking)

1. Per repository, list issues closed by a merged PR whose diff changes at least one test file and one non-test file.
2. Drop mechanically: body over 8,000 characters (`acceptance/contract.py:29`) or needing an image, non-test diff over
   150 lines, fix that adds a dependency.
3. Sort by close date, newest first. Take the first 4, 3, 3 (repositories in alphabetical order). No other skipping.
   The list goes into `PREFLIGHT.md`, committed before any job starts.
4. Argus receives the fix PR's **parent commit** and the issue's title and body, byte for byte. No comments, no PR text.

"Open" means open at the commit Argus sees. The maintainer's fix and tests stay unread until grading. Limit: recent
issues may still be in a model's training data.

## 4. Invocation and caps

One sandbox environment per repository (`scripts/build_env_from_base.sh`, then `scripts/check_env_image.py`), built
before selection. Per issue:

```
python scripts/argus.py code --repo ~/outside/<repo> --commit <parent-sha> \
    --issue-file <verbatim.txt> --environment <env> --max-usd 1.00
python scripts/argus.py status <job>
python scripts/argus.py approve <job> --sha <sha12> --max-iterations 3
python scripts/argus.py judge <job>
```

- Keys by `--key-file` with `--yes`, after one "go live" from Atha for the batch.
- No `--reference-patch`, no `--web`, no `--research`, no `redraft --note`.
- Approve rule: every draft the harness accepts is approved; Claude's own verdict is noted beforehand, for comparison.
- Allowed, and recorded: one plain `redraft` after `DRAFT_FAILED`, one `retry` after `AGENT_FAILED`.
- `applied` is never used. Stage caps as configured (`config.yaml:248-254`).
- Stop the batch at $8.00 real spend, or when one job passes $1.00.

## 5. Recorded per job

- Drafted (yes or `NO_DRAFT`, submits).
- Acceptance status of the run.
- Judge verdict.
- Hidden-test grade: `scripts/swe_grade.py` with the maintainer's tests (`resolved` or not).
- Draft tests green on the maintainer's fix (same script).
- Rubric grade A, B or C.
- Cost from the ledgers, failed stages and judge included.
- Interventions: redraft, retry, anything else.
- Human minutes; grading separately.

**Blind rubric.** A fresh Claude session sees issue and patch only, shuffled, without status or verdict; then the fix.
- **A, mergeable untouched:** `resolved`, same behaviour as the fix, no unrelated change, nothing shaped for the tests.
- **B, mergeable after a small change:** at most 10 changed lines, no logic.
- **C:** anything else.

## 6. Lines fixed before running

- **Kill: 2 or fewer A out of 10.**
- **Success: 5 or more A, at most $0.50 and 10 human minutes per A.**
- **3 or 4:** undecided; run a second batch of ten before changing anything.

Reasoning: the no-leak SWE runs resolved 8 of 14 (57%), on public instances and with reviewer steering. If the true rate
were 57%, 2 or fewer in ten happens about 2% of the time; if it were 20%, 5 or more happens about 3% of the time. Ten is
small: nothing finer than that can be read from it.

## 7. Safety and etiquette

- Local clones only. No push, fork, pull request, issue or comment by any automation.
- Offering a patch upstream is Atha's decision, by hand, with AI assistance disclosed and the project's policy read first.
- Repository code runs only in the sandbox; issue text and test output are untrusted data.
- Logs are searched for key prefixes before they are committed.

## 8. What each outcome changes

- **Kill:** stop hardening for the practice apps; drop planner, chain operator and UI phases 3-4; narrow the product to
  what still worked (failing-test reproducers, if drafts are mostly green on the maintainer's fix).
- **Success:** run the demand test with outsiders next; build `ReportConflict` and the verdict fix.
- **Undecided:** second batch; sort failures into drafter, agent and environment.

## 9. Defects to fix first

- **Run wedge (AUDIT D1): fix before.** Outside repositories bring unknown paths; a wedged job would be scored as Argus's
  failure.
- **Unlabelled `RunValidation` output (D6): fix before.** Outside test output is untrusted text.
- **Unknown cost charged as zero (AUDIT2 E1): not blocking.** Check `usd_complete` on every job and compare the total
  with the provider console.
- **Forgeable verdict (D5): not blocking.** The grade comes from the maintainer's tests and a reader, not from
  acceptance. The gap between `DONE` and `resolved` is itself a result.

## Sources (as given by Fable)

- SWE-bench (aiwiki); SWE-bench explained (codesota); cachetools README; cachetools on ecosyste.ms; cachetools Nix package; humanize on ecosyste.ms;
  python-humanize on Artix Linux; humanize LICENCE (Debian copy); mahmoud/boltons on GitHub, PyPI and ecosyste.ms.
