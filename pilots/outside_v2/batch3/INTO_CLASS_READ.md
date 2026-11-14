# Blind read of the 8 drafts made after INSERT-INTO against the maintainers' tests (2026-11-14)

Same protocol as APPEND_READ.md, no Argus money: for each of the 8 issues the drafter's block (from the INTO_CLASS_MEASUREMENT.md jobs; #1247 from its rerun, `j20261114_073301_0d2a`) and the lines the maintainers' PR added, as plain code blocks X and Y in random order (seed 20261115, key in `into_class_read/key.json`, written before the read), **shown with the indentation they have in the file** (so a block inside a class is indented like methods: placement is visible, unlike APPEND_READ.md). One Opus reader, read only (no code run, no git, key never opened) graded each block alone (catches the bug, over-specified, style, **placement**, grade A to D) and guessed the maintainers' block. Packet: `into_class_read/packet/`, grades: `into_class_read/opus_grades.json`.

| case | issue | where the drafter's block went | drafter | maintainers | drafter's placement | reader's guess |
|---|---|---|---|---|---|---|
| S01 | #1247 | into `NumericRangeTests` | B | A | right | right (medium) |
| S02 | #813 | into `ReplaceTests` | C | D | right | right (high) |
| S03 | #1152 | into `NumericRangeTests` | B | A | right | right (high) |
| S04 | #1250 | into `ValueChainTests` | B | A | right | right (medium) |
| S05 | #1098 | new class at the end | B | A | acceptable | right (high) |
| S06 | #1192 | into `InterleaveEvenlyTests` | B | A | right | right (high) |
| S07 | #1252 | new class at the end | C | B | wrong | right (high) |
| S08 | #849 | into `PeekableTests` | B | B | right | right (medium) |

**Drafter: 6 B and 2 C (APPEND_READ.md: 7 B and 1 D). Maintainers: 5 A, 2 B, 1 D (before: 6 A, 1 B, 1 D). Drafter's placement: 6 right, 1 acceptable, 1 wrong.** In 15 of 16 blocks the reader traces that the block catches its bug; the exception is the maintainers' block for #813 (only three changed `lambda *args: True` lines: tests neither the speed-up nor `default_arg`, graded D).

What the reader says is still wrong with the drafter's blocks: **calls wrapped in `try/except` re-raised as `AssertionError`** (a pattern the harness's red-by-assertion gate and the prompt itself ask for, see SPEC_DRAFTER_STYLE.md section 4), and **over-specification in 3 of 8**: S02 pins the exact padded arguments and predicate calls, S04 asserts CPython's `len()` error text, S05 requires an `mi.serialize` instance with `.lock`; S08 requires `types.GenericAlias`, which a `typing.Generic`-based fix would fail. The one wrong placement is #1252, whose tests belong in three classes (one entry per file).

What this does and does not say: the **placement problem is mostly gone** (the 7 of 8 "new class instead of extending the related one" of APPEND_READ.md became 6 of 8 right), but the **overall grade did not move**: 6 B, 2 C against 7 B, 1 D, and the reader again told the two authors apart 8 of 8 (the indentation of a block makes placement visible, which also makes the author easier to guess). The two readings are not a controlled comparison: the packet format differs, #1247 is a rerun, the reader is one model, n = 8 in one repository, one run per issue. The remaining quality gap is not placement but over-specification and the red-by-assertion style, which an `insert_into` cannot fix.
