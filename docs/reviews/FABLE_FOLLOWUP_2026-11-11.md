> Verbatim copy of Fable's `FOLLOWUP.md`, pasted by Atha on 2026-11-11 and not edited. Claude's reading of it, with what was checked
> against the repository, is in [`FABLE_REVIEW_2026-11-11.md`](FABLE_REVIEW_2026-11-11.md). It follows
> [`ARCH_REVIEW_2026-11-11.md`](ARCH_REVIEW_2026-11-11.md).

# FOLLOWUP: code reading behind ARCH_REVIEW (main 3d3b078)

Read in full: `codetask/run.py`, `codetask/agent.py`, `acceptance/verdict.py`, `router/job.py`, `codetask/status.py`, `acceptance/testdetect.py`, `acceptance/leaks.py`. Nothing was run. Not read: `harness/guard.py`, `harness/steps.py`, `codetask/tools.py`; points resting on them are marked "delegated".

## 1. Guarantees

- **Refuse-before-send:** delegated; the agent's only model call is `caller.call` (`agent.py:382`). Attempts are admitted from the ledger (`run.py:176-183`, `286`, `382`); a stage cap is `min(stage, job cap − ledger spend)` (`job.py:680`, `850`, `1198`), reused on resume (`job.py:686`, `931`).
- **Send first, check later exists:** `EstimateExceeded` is handled after the money is spent (`run.py:442-455`; conceded at `run.py:12-13`).
- **Step memo keys:** upheld (`agent.py:375`, `416-417`, `326`, `341`).
- **Reservation from ledger:** upheld (`agent.py:307`).
- **By convention only:**
  - Tool versions are hand-bumped literals (`run.py:208-209`); one is patched into a shared dict after the closure captured it (`run.py:331`).
  - "Every tool is safe to repeat" is a docstring (`agent.py:4-6`).
  - Money is float at the edges (`run.py:87`, `job.py:534`, `680`); only comparisons use nano (`run.py:181`, `job.py:206`).
  - The human: `by` is `$USER` (`job.py:887`); `--yes` records "approved in chat" (`job.py:411-414`).

## 2. ARCH_REVIEW claims

- "`durability="sync"` at all four `graph.invoke` sites": **confirmed** (`run.py:436`, `440`).
- "the agent … has no way to say 'I am stuck'": **confirmed**. "Fix the code, not the tests" (`agent.py:172`); three claim kinds (`agent.py:175`); no fitting terminal reason (`status.py:29`).
- "The regex gate will be bypassed by the next variant": **confirmed, and worse**. A hit is an ordinary failed criterion (`verdict.py:31`); its reason, with the matched lines, is fed to the next attempt (`run.py:386`, `agent.py:495`).
- "No judge verdict is recorded…": **strengthened**. The judge is opt-in (`job.py:996`); `applied` never reads it (`job.py:1302-1321`).
- "record the approver's identity … now": **weakened**. Decisions are already logged with time and `by` (`job.py:153-155`, `887`, `1319`); missing is a `by` that tells Atha from Claude.
- "Atha's real time: not recorded anywhere": **partly contradicted** (see 4).

## 3. The "blocked by locked test" exit

A `ReportConflict` tool beside Finish ends the attempt (`agent.py:429-431`); acceptance verifies it (`run.py:366-384`). Today every non-DONE becomes `AGENT_FAILED`, which offers a useless `retry` (`job.py:939-940`, `1511`).

```python
# agent.py:429
if record.get("conflict"):                  # committed like Finish
    return end("conflict_reported", step, conflict=record["conflict"])
# run.py, after evaluate() (353)
c = (state.get("attempt") or {}).get("conflict")
if c and v["outcome"] == "fail":
    red = failing_tests(v)                  # harness evidence, not the claim
    ok = (set(c["tests"]) == red            # nothing else is red
          and all(protected_and_old(t) for t in red)
          and passed_at_baseline(red)
          and required_tests_pass(v)        # must_pass all green
          and scope_and_detection_pass(v))
    if ok:
        return move(state, st.BLOCKED, blocked="test_conflict",
                    verdict={**summary, "conflict": sorted(red)}, failures=history)
# unverified: an ordinary failed claim
# status.py:29: add "test_conflict"; job.py:939: new state CONFLICT, package built, no retry
```

The human sees the named tests, their failing assertions, the patch, and the wording of `_conflict_refusal` (`job.py:724-731`).

Riskiest:
1. **Lazy exit.** The checks prove "new tests green, only named old tests red", not that the old test is wrong; a real regression passes them.
2. **Injected or flaky trigger.** Repository text can tell the agent to report; a flaky old test changes the status across a resume, since acceptance reruns (`run.py:353-362`).
3. **Dead end.** `redraft` is refused here (`job.py:1232`), so each conflict costs a new, unlinked job.

## 4. Measurement and the chain operator

Recoverable from `job.json`:
- Decisions: `confirmed`/`confirmed_by_flag` (`job.py:414-418`), `research_ok` (`665`), `approved` (`889`), `retry` (`1216`), `redraft` (`1235`), reject/abandon (`1279`, `1292`), `applied` (`1318`).
- Minutes, upper bound only: `approval.at` (`886`) minus draft `ended_at` (`709`); `applied` minus agent `ended_at` (`937`). Under `--yes` the confirm interval is zero.
- Outcome and cost: `as_is` (`1319`); stage `usd` (`709`, `937`, `1060`).
- Missing: a link between jobs re-issued for one issue.

A chain operator would be the first router code to write to a target repository; today apply is printed (`job.py:1376-1382`). It breaks "a job has one cap" (`job.py:18-21`, `205`), the per-job lock (`157-172`) and "the router calls no model" (`15`). It needs its own job kind (`142-147`); job B still needs approve by sha (`833`).

## 5. The two fences

- **Detection gate:** unavoidable where it sits, but it should be terminal, not feedback. Open: suffix allowlist (`testdetect.py:17`, `84`); name-only exemption, so `conftest.py`, any `test/` directory and `*.spec.*` are skipped (`34-39`); pre-existing matching lines are subtracted (`102-109`). Unreadable and oversized files fail closed (`89-92`).
- **Leak warning:** any exception returns no finding (`leaks.py:70-71`) and nothing is printed for none (`job.py:798-803`), so "clean", "crashed" and "not Python" look the same. Under `--yes` the screen is only echoed (`job.py:412`).

## Surprises

- `applied` reads the patch from the recorded absolute directory (`job.py:1311`); the judge deliberately does not (`982-989`).
- `applied` accepts any commit; neither its parent nor its tests are checked (`1313-1319`).
- API keys stay in `os.environ` for the whole stage (`job.py:449-456`) while children are spawned; scrubbing is outside these files.
- `recursion_limit` is a literal 40 (`run.py:420`); `max_iterations` comes from the contract.
