# PRD writer pilot 1 (athena), 2026-11-16

n = 1, kept apart from the scoreboard figure. First use of `argus prd new` (docs/reviews/SPEC_PRD_WRITER.md, PRs #566, #568).

**Input** (`pilot1/message.txt`): one rough wish in Indonesian, written by Claude as a stand-in for the human (so this is not yet "the human wrote the wish"): an open-positions summary for the athena journal, backend only.

**What the writer produced** (`pilot1/`, unedited): `PRD.md`, `issues.json`, one issue (`GET /journal/open-summary`, 9 rules with examples, 4 test scenarios). It declared the path with `via_proxy: false` and wrote in the PRD that the viewer proxy does not forward it (a hidden dependency B1 exists for; nobody asked for it). `prd check`: no BLOCK, no WARN.

| Step | Job / queue | Result | Cost |
|---|---|---|---|
| PRD turn w1 (Haiku 5.5) | j20261116_070355_87c9 | 3 submits (1 style, 1 folder check), 0 clashes | $0.0193 |
| Draft | j20261116_071947_0332 | DRAFTED, 5 red tests, no redraft | $0.0255 |
| Agent | same | DONE in 10 steps, no retry | $0.0078 |
| Apply | queue q20261116T071852Z-825b | APPLIED c82cd47 (athena master, not pushed) | |

Total $0.0527 (PRD $0.0193 + code job $0.0334). Evidence after apply: athena's full suite in its own venv, 908 passed, 0 failed (903 before; +5 new tests; not the sandbox run).

Human actions (Atha, in the chat): one `prd approve` (decided with "approve langsung"), one `queue go`, one draft approve, one apply. Claude ran the commands and read the PRD, the draft and the production diff of the patch.

**Not shown by this pilot**
- Only ONE issue: the ordering rule (`creates` before `touches`) was not exercised in a real run; it needs a PRD of two or more issues.
- The wish was written by Claude, not by Atha. "Without Claude" is not measured.
- Whether Haiku writes PRDs as well as Claude does: n = 1, and Claude's own six issues went through no `issue_gate`, so there is no like-for-like baseline.
- The draft's one gap (scenario d did not say today's date) was closed by the drafter itself, not by the PRD.
- No frontend (sandbox has no node, see PENDING parkiran).
