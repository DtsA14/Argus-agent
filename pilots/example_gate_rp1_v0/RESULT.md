# Example gate: the Rp1 case again (athena before the change, 2026-11-17)

Closing evidence of T1 (SPEC_EXAMPLE_GATE). n = 1. Base: athena at `c82cd47` (before `705db5b`, the change that lowered `IDX_MIN_PRICE` to 1.0), environment `athena_py312`, cloned to a scratch repository; the original message of the first pilot (`message.txt`) is used as it was. Run from the deployed checkout (`main` at `f6c0311`, PR 3).

## A. The issue writer, through the gate (`issue_from_writer.txt`)
- Job `jrp1_pilot`, one turn (w1), Haiku 5.5: WRITTEN, **$0.0177**. 19 tool steps, of which 4 were `RunExample` (the writer ran its examples on the real code before writing them). Two submits: the first was rejected for static reasons only (no `Tests:` paragraph; it claimed the old tests keep passing while naming clashes), the second passed.
- The block the harness wrote has 3 examples, all true on the base commit: `e1` whatif (floor 1.0): entry 50.0, ATR 3.0 gives not blocked, 200000 shares, **stop 45.0** (the number the first pilot's writer got wrong as 47.0); `e2` whatif: entry 1.0 is blocked with 0 shares; `e3` same: today a Rp50 stock is blocked.
- So here the gate caught nothing in the numbers: the tool had already shown the writer the real values. What it adds is that every number in the block is machine-checked, and the three clashes the writer found (tests at lines 535, 552, 565) are the same three as in the first pilot.

## B. The four wrong numbers of the first pilot, written by hand (`issue_wrong_numbers_by_hand.txt`)
Sent through `argus code` (intake gate, no model called, **$0**): the job was `BLOCKED` before any drafter money, naming the real values:
- `e1` entry 0.5: expected blocked, the code gave `ZeroDivisionError: float division by zero`;
- `e2` entry 1.5: expected 1,000,000 shares, the code gave 1,304,300 (stop 1.0);
- `e4` stop 47.0: the code gave 45.0.
- `e3` (entry 1.2, rounded to 1 and then blocked) is **right** on the real code, so it passed: three of my four hand-written examples were wrong, and all three were caught. The spec said three of the four original numbers can be expressed; this is those three.

## What this does not show
- The number of wrong numbers a real writer makes with the gate is unmeasured (n = 1, and the writer used `RunExample` first). The hand-written block shows detection, not frequency.
- Numbers in the prose of the issue (the rules) are not checked, only the examples block; here the prose numbers agree with the block.
- The issue was not taken further (no draft, no agent, no apply): the audit after the agent (PR 2) was not exercised on this case.

## Deploy note
The live checkout (`pilot3a_live`) had no `.sandbox_image_*` pin files (git-ignored), so an athena or ledger issue job from the chat would have been refused at the pin; they were copied from the other checkout. Any new checkout that serves the chat needs them.
