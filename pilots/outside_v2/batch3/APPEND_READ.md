# Blind read of the 8 appended test blocks against the maintainers' tests (2026-11-14)

What: for each of the 8 batch 3 issues, the test block the drafter appended (see APPEND_MEASUREMENT.md) and the test lines the maintainers added in the fix PR, as two plain code blocks X and Y in random order (seed 20261114; key in `append_read/key.json`, written before the read). One Opus reader, read only (no code run, no git, key never opened), graded each block alone on: catches the bug, over-specified, style fit with `tests/test_more.py`, grade A to D, and guessed which block is the maintainers'. Packet: `append_read/packet/`; grades: `append_read/opus_grades.json`. Cost: tokens of one subagent, no Argus money.

| issue | drafter block | maintainer block | reader's guess |
|---|---|---|---|
| #813 replace | D | D | right (medium) |
| #1252 split maxsplit | B | B | right (high) |
| #1247 numeric_range | B | A | right (high) |
| #1192 interleave_evenly | B | A | right (high) |
| #1152 numeric_range reversed | B | A | right (high) |
| #849 peekable subscript | B | A | right (high) |
| #1098 synchronized | B | A | right (high) |
| #1250 value_chain | B | A | right (medium) |

**Drafter: 7 B, 1 D. Maintainers: 6 A, 1 B, 1 D.** The drafter's block catches the bug in 7 of 8 cases (reader's trace by reading, not by running); the D is #813, where the test requires the padding semantics of a new `default_arg` keyword that the issue never defines and could reject a correct fix (the maintainers' block for #813 also got a D: the reader found it only makes sense as part of a diff, so one D is partly a packet artefact).

What the reader says is wrong with the drafter's blocks (7 of 8 cases): a **new standalone TestCase class** instead of extending the related one (`SplitBeforeTest`, `NumericRangeTests`, `InterleaveEvenlyTests`, `ValueChainTests`, ...), and `try/except Exception -> AssertionError` wrappers the file does not use. That is the placement and style problem the later `insert_into` idea is about; the append rule moved the tests into the right file but not into the right class.

Caveats: the two kinds of block were told apart 8 of 8 (so the grade of a block is not independent of knowing its author's style, though the reader did not know which was which when grading); one reader, one model; grades by reading only; the maintainers' blocks are the added lines of the PR without their context (for #813 and #1252 the PR also changed existing tests, not shown); n = 8 in one repository.
