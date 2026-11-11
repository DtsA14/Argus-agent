# PREFLIGHT (DRAFT): the ten issues of the retrospective outside experiment, by the fixed rule

Status: **draft, not final**. Prepared 2026-11-11 by Claude from GitHub metadata only (issue list, closing PR, file names and line counts of the fix PR, the parent commit of the merge).
**No maintainer fix, test or issue comment was read**, and no job was run. It becomes the final `PREFLIGHT.md` only after Atha decides the open points below and it is committed **before the first job**.
Protocol: `docs/reviews/FABLE_PROTOCOL_OUTSIDE_EXPERIMENT.md` section 3. Data and script: `preflight_scan.json`, `preflight_scan.py` (GitHub GraphQL, `closedByPullRequestsReferences`; read only).

## Rule as applied

1. Issues closed by a **merged** PR of the same repository (GitHub's closing-reference link), closed on or after 2025-11-11.
2. The fix PR changes at least one test file and at least one non-test source file (docs, `.md`, `.rst`, `.txt` excluded); non-test diff at most 150 lines; issue body at most 8,000 characters; the PR touches no
   dependency or build configuration (`pyproject.toml`, `setup.py`, `setup.cfg`, `requirements*`, `tox.ini`).
3. **One issue per fix PR** (an amendment found while building this list: several issues are closed by the same PR, for example boltons #480 and #479 by PR 610, and #343 and #333 by PR 425; the newest closed is kept).
4. Newest close time first; take the first N per repository.
5. Argus receives the **parent commit of the merge** (`git rev-parse <merge>^1`, from the API) and the issue title and body byte for byte.

## Variant 1: two repositories, five issues each (recommended: no harness change)

| Issue | Closed | Fix PR | Parent (12) | Title |
|---|---|---|---|---|
| mahmoud/boltons#480 | 2026-10-25 | #610 | `fe1ce8bcc4df` | FilePerms cannot revoke permission bits: setting a field to a subset of its value is a no- |
| mahmoud/boltons#439 | 2026-09-07 | #440 | `efff866a3b66` | IndexedSet: difference_update/intersection_update are quadratic for large removals |
| mahmoud/boltons#261 | 2026-08-07 | #445 | `78e8638e695d` | Python `funcutils.wraps` breaks when keyword only arguments involved |
| mahmoud/boltons#343 | 2026-07-18 | #425 | `289edfcd2047` | wraps loses keywords |
| mahmoud/boltons#383 | 2026-07-17 | #416 | `ebc7a8f776de` | Supporting more PathLike in path-related methods |

| Issue | Closed | Fix PR | Parent (12) | Title |
|---|---|---|---|---|
| more-itertools/more-itertools#1344 | 2026-11-04 | #1345 | `08dca284ba54` | numeric_range equality and hashing overflow for lengths above sys.maxsize |
| more-itertools/more-itertools#1308 | 2026-10-07 | #1309 | `1ea82a711c69` | bucket ignores a supplied validator when the callable is falsey |
| more-itertools/more-itertools#1304 | 2026-09-29 | #1305 | `790bb0bb2c03` | ichunked(..., 0) raises islice's ValueError on a nonempty iterable |
| more-itertools/more-itertools#1293 | 2026-09-25 | #1294 | `670b715b307a` | Repeated zero-cache seekable.peek() retains nested chain iterators |
| more-itertools/more-itertools#1275 | 2026-09-17 | #1276 | `3ea9b009b19d` | numeric_range reverse iteration changes float values and overflows at datetime limits |

## Variant 2: three repositories, 4 / 3 / 3 in alphabetical order (needs the `src`-layout handling for cachetools, `-o pythonpath=src`)

| Issue | Closed | Fix PR | Parent (12) | Title |
|---|---|---|---|---|
| mahmoud/boltons#480 | 2026-10-25 | #610 | `fe1ce8bcc4df` | FilePerms cannot revoke permission bits: setting a field to a subset of its value is a no- |
| mahmoud/boltons#439 | 2026-09-07 | #440 | `efff866a3b66` | IndexedSet: difference_update/intersection_update are quadratic for large removals |
| mahmoud/boltons#261 | 2026-08-07 | #445 | `78e8638e695d` | Python `funcutils.wraps` breaks when keyword only arguments involved |
| mahmoud/boltons#343 | 2026-07-18 | #425 | `289edfcd2047` | wraps loses keywords |

| Issue | Closed | Fix PR | Parent (12) | Title |
|---|---|---|---|---|
| tkem/cachetools#443 | 2026-10-19 | #445 | `eba200635273` | @cachedmethod decorator breaks mock autospec |
| tkem/cachetools#440 | 2026-10-15 | #441 | `f4f288579dc3` | Failed TTL expiration calculation leaves an unusable cache entry |
| tkem/cachetools#435 | 2026-10-15 | #436 | `0985ec0d8fef` | cachedmethod class access loses the explicitly supplied instance |

| Issue | Closed | Fix PR | Parent (12) | Title |
|---|---|---|---|---|
| more-itertools/more-itertools#1344 | 2026-11-04 | #1345 | `08dca284ba54` | numeric_range equality and hashing overflow for lengths above sys.maxsize |
| more-itertools/more-itertools#1308 | 2026-10-07 | #1309 | `1ea82a711c69` | bucket ignores a supplied validator when the callable is falsey |
| more-itertools/more-itertools#1304 | 2026-09-29 | #1305 | `790bb0bb2c03` | ichunked(..., 0) raises islice's ValueError on a nonempty iterable |

## Points for Atha (and Claude) before this is final

- **Which variant.** Variant 1 needs no harness work; variant 2 needs a decision on `src` layout first (`ENV_SPIKE.md`).
- **Possible contamination.** All selected issues were closed between 2026-01 and 2026-11, so the models may have seen some of them or their fixes; the protocol already names this limit. Several `more-itertools` issues read as
  structured bug reports with small fixes (4 to 53 changed lines): they are probably easier than the average issue, so a success rate here is an upper bound.
- **Fresh grader.** The grading session must be a fresh Claude session that has not seen this list's fix PRs; the fix PR numbers above are metadata for the grading script only.
- **Full SHAs** and issue bodies are fetched at the moment of the run (not stored here, to keep the list small); each job records them.
- **Environments:** boltons and more-itertools run with Argus's own command and no option; their sandbox environment entries are still to be written (strict lane).
- Not applied here: the "issues written by users" criterion (some bodies are maintainer-written); it is a judgement, not a mechanical filter.
