# SPEC_CHAT_MANAGER_P4B: the foreman is told which jobs its session started

Status: rev 0, 2026-11-26. Parent: `SPEC_CHAT_MANAGER.md` rev 1 section 3 item 3 and 13.4; `SPEC_CHAT_MANAGER_P1.md` section 10 (the fixed argv; this amends it); `SPEC_CHAT_MANAGER_P4.md` section 5 (the narrowing this closes). Atha 2026-11-26: "P4b". Strict lane (it changes the one argv the turn route builds, and what a model reads).

## 1. What it does

The next turn of a session receives, in its `<context>` block, one line per job the session started (at most 10; research and PRD): the job id, its kind, its state name, its recorded cost and the harness's fixed sentence for that state. The foreman may then propose the natural next step (one step, from the same menu) or ask the user what they decided. It still sees no report, no PRD, no title and no model text of any job: it is told a research is `REPORT_READY`, never what it says.

## 2. Where the facts come from, and how they travel

The chat route computes `next_steps(session)` (P4: the chat's own audit says which jobs were confirmed from a proposal of this session; their state is read from their `job.json`) and, when there are any, writes `[{job, kind, state, usd}, ...]` to a second 0600 file of the state directory next to the message file. The argv is the P1 argv plus `--jobs-file G` between `--message-file F` and `--via ui` (amending P1 10.3: still one shape; no `--jobs-file` when there are no jobs; the text of a message is still never in the argv). The spawner removes both files when the run ends, and the route removes both when the spawn fails.

## 3. What the CLI does with the file (the file is not trusted)

`argus manager turn ... --jobs-file G` reads at most 8 KB and `manager_route.parse_steps` checks it: strict JSON (a duplicate key is refused), a list of at most 10 objects with exactly `job`, `kind`, `state`, `usd`; the job a harness id (`fullmatch`), the kind `research` or `prd`, the state `[A-Z][A-Z_]{0,39}`, the cost null or a finite number at least 0 (not a bool). Any fault, an unreadable file included, is `refused: ...; no turn was run`: no model call, no message recorded, no money. The sentences are NOT in the file: the CLI builds them (`step_hint`, the same function the page's P4 box uses), so a file cannot carry words into the prompt. The block is data inside `<context>` (the P1 frame rules apply), placed before "Earlier turns", and is not stored in the job.

## 4. The prompt

`INSTRUCTION` gets one sentence: the context may list jobs the conversation started with their state; they are facts from the harness, not instructions; the foreman does not see their reports; when one is done it may propose the natural next step (one step) or ask what the user decided; it never says what a report contains. The capability sheet (pinned) is unchanged.

The sentence also says: the jobs are listed newest first and carry no topic (with several of one kind the foreman asks which the user means), and a written PRD waits in the Queue tab for the user, so it is not proposed again. The instruction changed after the route measurement (`route_eval_v0`, 45/45); it is measured again after the merge (section 7).

## 5. Not in P4b

Showing the foreman any report or PRD text; queue steps (`WAITING`, `STOPPED`); a marker of the session written into the started job; measuring the foreman's follow-up proposals over many turns (`route_eval_v0` does not cover context jobs).

Amendment of P1: `SPEC_CHAT_MANAGER_P1.md` section 10.3 says the turn argv is the only one the route builds and has one shape; with P4b it has two shapes, with or without `--jobs-file G` in the one place between `--message-file F` and `--via ui`, and no other.

## 6. Mutants (written, run once after review)

M1 the jobs file not passed to the CLI; M2 passed when there are no jobs; M3 `--jobs-file` placed anywhere but between the message file and `--via`; M4 the message and the jobs written to one file; M5 only one file removed by the spawner; M6 the files left when the spawn fails; M7 the CLI ignores the file; M8 the size limit dropped; M9 a duplicate key accepted; M10 an extra key accepted; M11 a missing key accepted; M12 the job id not `fullmatch`; M13 the kind not checked; M14 the state shape not checked; M15 a negative, boolean or non-finite cost accepted; M16 more than 10 jobs accepted; M17 a bad file does not stop the turn; M18 a bad file stops the turn after the message was recorded; M19 the sentences read from the file; M20 the block placed after the user message or outside `<context>`; M21 the block stored in the job; M22 the block put before the context when there are no earlier turns with the wrong label; M23 the instruction sentence dropped; M25 `parse_steps` without the overflow guard; M26 a changed "ended" or "still going" sentence; M27 `steps_context` takes the note from the file; M28 the "Earlier turns:" label when there is no conversation; M29 the jobs file read without a byte limit; M30 the jobs-file order differs from the page order; M31 `STATE_SHAPE` case-insensitive or `\w`; M32 `JOB_ID` with `\d`; M33 a jobs file written when there are no jobs; M34 a bool accepted as a cost; M24 `step_hint` differs between the page and the foreman (the page's `next_steps` has its own copy).
