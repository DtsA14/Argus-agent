> Verbatim copy of Fable's `PLAN.md` (planning session), pasted by Atha on 2026-11-11 and not edited, apart from this note. **Proposal, not adopted.** Claude's assessment, the changes
> Claude proposes, and the decisions needed from Atha are in section 14 of [`FABLE_REVIEW_2026-11-11.md`](FABLE_REVIEW_2026-11-11.md).

# PLAN: what to do with the 2026-11-11 reviews

Fable, against `origin/main` d2ecced, from `FABLE_REVIEW_2026-11-11.md` sections 1-13, `PENDING.md` and
`Reconciliation.md` 6-7. No code re-audited. "Verified" means Claude checked it.

## 1. Backlog

Effort: S under half a day of Claude time, M about a day, L several days.

| Id | Item | Lane | Needs | Size | Who | Done when | Moves |
|---|---|---|---|---|---|---|---|
| SB | Scoreboard script from `job.json` and the ledgers | fast | – | 1 PR, S | Claude | `verification/scoreboard-<date>.json`; counts equal the scan (119 code jobs, 62 applied) | Cost per applied change, failed jobs included (C3, C9) |
| DOC | Corrections C1, C2, C4, C6-C8, C11, C12; stale `PENDING.md` lines; mutant logs for #436/#437 saved | docs | SB | 1 PR, S | Claude | Two `*_mutants.log` files; numbers cite the scoreboard file | 12 stale claims to 0 |
| FIX-A | D1 run wedge + D6 `RunValidation` label (same file); attacks A8, A7 as tests | strict | – | 1 PR, M | Claude; Atha merges | Tests fail on old code; verify log | D1, D6 (verified) |
| ENV | Measure three candidates, confirm the boltons licence, three sandbox environments | strict | – | 1 PR, M-L | Claude; Atha merges | Three passing `.check.json` records; suite times in a file | G4, G6 (**cost unverified**) |
| PRE | `PREFLIGHT.md`: ten issues by the fixed rule; grading directories | experiment | ENV | S | Claude | File committed before the first job | Selection rule |
| EXP | Run and grade the ten | experiment | FIX-A, PRE | M | Claude runs; fresh Claude session grades; Atha: "go live", verdict | `pilots/outside_v0/RESULT.md` with A/B/C counts | Unassisted success rate: unknown to a number |
| FIX-B | E1 unknown cost charged as zero + E2 non-positive prices | strict | – | 1 PR, S | Claude; Atha | Tests fail on old code; verify log | E1, E2 (verified) |
| RC | `ReportConflict` MVP (v2, F6), attack A11 as a test | strict | EXP not "kill" | 1-2 PRs, L | both | Replay fixture of `c4be` ends `BLOCKED/test_conflict` | The five-incident class gets an exit |
| GATE | Detection-gate hit becomes terminal | strict | RC | 1 PR, S | Claude; Atha | Test: a hit ends the run with no feedback | B6 |
| VF | Verdict forgery: forger fixture first (A10), then canary-and-nonce spec | strict | EXP false-pass count | 1 spec, 1 PR, L | both | Forger fixtures fail acceptance | D5 (**unverified**: never executed) |
| FIX-C | D2 ledger fsync + D7 key redaction (A9 as test) | strict | – | 1 PR, M | Claude; Atha | Tests fail on old code; verify log | D2 (verified); D7 leak path **unverified** |
| GUARD | Phone page shows `for_human` beside new test names and changed files | fast | – | S | Claude | Viewer release shows all three | A13 (H3) |
| ADV | Advisory lane in `AGENTS.md`; under it `leaks` says "not checked" (B12); `smoke_models.py` exempted (D3) | docs | Atha | S | both | `AGENTS.md` diff merged | Ceremony cost |

## 2. Order

**Phase 1: measure what exists, unblock the experiment.** SB and DOC first (no waiting). FIX-A and ENV in parallel;
while each waits on its `verify_at`, write GUARD and PRE.
*Exit:* the scoreboard file, FIX-A's verify log, three passing environment checks and `PREFLIGHT.md` all exist.

**Phase 2: the outside experiment.** EXP, with FIX-B alongside (it gates nothing).
*Exit:* `RESULT.md` with the count of A, cost per A, human minutes and Atha's verdict.

**Phase 3: depends on the verdict** (section 3). On success: RC, GATE, VF, FIX-C in that order.
*Exit:* RC merged with its replay test, or a dated decision in `PENDING.md` to narrow the product.

## 3. Decisions for Atha

| When | Evidence in front of him | Answers |
|---|---|---|
| Now | This plan; #437's cost (spec, 25 mutants, verify, for an advisory warning) | Advisory lane yes: ADV proceeds. No: B12 is dropped |
| End of phase 1 | `PREFLIGHT.md`: ten issues, three environment checks, caps ($1.00 a job, $8.00 a batch) | "Go live" for the batch, or replace a repository |
| End of phase 2 | `RESULT.md` beside the scoreboard baseline | **2 or fewer A: kill.** Stop the hardening queue after FIX-B; no RC, GATE, VF; decide between failing-test reproducers (if draft tests were mostly green on the maintainers' fixes) and the harness as a library. **5 or more A: success.** Phase 3 as written; decide on reproducer PRs under his GitHub name. **3 or 4:** second batch of ten; build only what fixes the largest failure class |
| On success only | Patches graded A | Offer any upstream, by hand, disclosed: yes or no |

## 4. Cut, stop, do not start

- **Stop:** spec and mutants for advisory output; hand-written status numbers; issue-writer latency tuning; a regex
  fence per incident.
- **Drop from the backlog:** running A13 (it succeeds by design; do GUARD instead); the `applied` judge warning (B7: the
  judge ran on 8% of code jobs); a code change for `smoke_models.py`; D8-D11, E4, E5; the A2-A6 batch. None moves a
  measured number.
- **Freeze:** new research-line work until the phase 2 verdict.
- **Do not start:** M4 (reopen: a job class one agent fails and a hand-split passes); M7 (a second approver); M8
  (recurring failures no check can encode); planner (two chains with glue rated "not automatable"); UI phase 3 (Atha
  rejects 4 of 5 planted bad drafts from the phone); UI phase 4 (a second operator); chain operator (a second chain).

## 5. Where I differ from Claude's order

- **Regroup the first PRs.** D1 and D6 gate the experiment and share a file: one PR. E1 and E2 are money and gate
  nothing: a separate, later PR. Bundling D1 with them lets a money review hold the experiment.
- **Experiment before `ReportConflict` and the verdict fix.** Both are L, strict, and wasted on a "kill". The
  experiment supplies their evidence: how often only old tests are red, how often `DONE` is not `resolved`.
- **D2/D7/D3 are not one batch.** D3 is a sentence in `AGENTS.md`. D2 and D7 go last.
- **Scoreboard first:** agree. **A13 early:** disagree; skip the run.

## 6. Risks to this plan

| Risk | First signal |
|---|---|
| ENV costs more than a day (unverified) | First environment not passing its check in one session: fall back to one repository, four issues |
| Running before RC scores conflicts as failures | Two or more of ten end `FAILED_ACCEPTANCE` with only old tests red: RC moves ahead of batch two |
| FIX-A is too narrow | Any traceback in an experiment job log |
| High score from memorised fixes | More than half the A patches identical to the maintainer's: treat success as unproven |
| The middle outcome is likely | At a true rate of 35%, 3-4 A is about as likely as not: budget a second batch now |

## 7. Contradictions and a rule

- `PENDING.md` L99: scoreboard, experiment and attack designs "not done"; review sections 11-13 show them designed.
- `PENDING.md` L93 calls the whole block strict lane; the scoreboard is read-only.
- `PENDING.md` lists RC and the verdict fix before the experiment; section 11 gates the experiment on D1 and D6 only.
- Section 10 batches D1 with E1/E2; section 11 names D1 and D6 as the gate. This plan follows section 11.
- `Reconciliation.md` is unchanged since the reviews: "J9 in use" (the judge ran on 10 of 119 code jobs), UI phases 3-4
  "awaiting Atha" (now on hold), none of C1-C12 applied.

**Rule:** a number in a status document is copied from a generated file under `verification/` and cites it; a number
without a source is deleted. `PENDING.md` holds open items only, by the ids above.

## 8. Schedule

Assumes Claude's working time tracks Atha's hours; Claude's time, not Atha's, bounds phase 1.

| Atha per week | Week 2 | Week 4 | Week 8 |
|---|---|---|---|
| 6 hours | Phase 1 exit | Phase 2 exit (verdict) | On success: RC and GATE merged, VF specified. On 3-4: second batch graded |
| 2 hours | SB, DOC, FIX-A merged | Phase 1 exit | Phase 2 exit (verdict); phase 3 not started |
