# ledger-cli pilot: the first repo Argus builds from a scaffold (2026-11-19)

Why: Atha wants T6 (new repos from a prompt) fast and real use instead of more gates (AGENTS.md, "Proportional process and real use first"). This
pilot is the first real task, chosen because its result is objective: a CSV expense analyzer with numbers that can be computed by hand.
This file is the living record of the pilot. Update it as the pilot goes; keep it factual.

## Setup (what was done by hand, and is what `argus env init` / T6 should automate)
| Step | What | Where |
|---|---|---|
| Scaffold | package `src/ledger_cli`, one passing test, `pyproject.toml` with pytest `pythonpath`, README, `.gitignore`; one commit | `~/ledger-cli` (local, not pushed) |
| Registration | one line in `issue_writer.repos` (`ledger-cli`, environment `ledger_py312`, reused image: Python 3.12 + pytest) | `config.yaml`, PR #631 |
| Environment | no new image: the stdlib-only project reuses `ledger_py312` | `.sandbox_image_ledger_py312` pins already in `pilot3a_live` |
| Request | Atha's spec (CSV format, rules, command contract, JSON shape, exit codes) in Indonesian, 2,358 characters | `~/ledger_request.txt` |
| Hidden tests | 12 acceptance tests and 7 CSV fixtures, written from hand-computed numbers BEFORE Argus started, outside the repo; they use only the command contract | `~/ledger_eval/`, hash of fixtures + tests `d1c1d01e20c0901bbfb618b4c39d145fb7968d78d8e6ce2356fdfa64068dc7e8` |

The hidden tests were first run against a small reference implementation of mine (12 passed) to check the tests themselves, then the reference was deleted.
Run them at the end with `LEDGER_REPO=~/ledger-cli pytest ~/ledger_eval/test_ledger_cli_acceptance.py`. They are written by Claude: a smoke test of the
cases Claude thought of, not proof of correctness.

## What is measured (agreed with Atha)
Product verdict (separate from process verdict): hidden tests passed, with a comment on the structure.
Process: issues that reach APPLIED; operator steps typed by Claude (log below); total money; times Atha was confused by a card; Atha tries the tool himself.

## Operator log (every command Claude typed; Atha's gates marked)
Kept in `~/ledger_ops.log` (60 lines for the whole pilot, 2026-11-19; not in the repository). Kinds of command Claude typed:
`prd new`, `prd check`, `prd approve` (Atha), `queue go`, `queue step`, `approve` draft (Atha), `patch-read-run`, `apply` (Atha), `queue step`
(blocked by the example gate), `prd reply --rebase`, `queue close`, `prd reply` again, `prd check`, `prd approve` and `queue go` for the rewritten PRD (Atha), `queue step`.

## Result (2026-11-19, one afternoon)
**Product verdict: passed.** All 5 planned code issues reached APPLIED in `~/ledger-cli` (commits `5e0484c`, `f61899e`, `367291e`, `d783ae4`, `f502f11`; local, not pushed).
The 12 hidden acceptance tests (written before Argus started, hash `d1c1d01e...` unchanged) pass: 12/12. Argus' own 35 tests pass. The CLI prints a readable summary, writes the
JSON of the contract, exits 0/1/2 and names the line of a bad row. Limit: the package is in `src/`, so `python -m ledger_cli` needs `PYTHONPATH=src` or an install; the README does
not say so (the scaffold was Claude's choice; the hidden tests set the path). The hidden tests are Claude's, a smoke test of the cases Claude thought of.

**Process verdict: the path works end to end but is far from hands-off.**
| Measure | Result |
|---|---|
| Issues APPLIED of planned | 5 of 5 (after 3 PRD rewrites) |
| Commands Claude typed | about 50 operator steps (`~/ledger_ops.log`), plus 4 fresh Claude sessions as second domain readers |
| Atha's gates | PRD approval x4, draft approval x5 (one per issue), apply x5, reject x1 (plus several "ok/setujui" answers) |
| Money | PRD writer $0.0717 (4 turns); code jobs $0.063 (draft + agent); patch readers about $0.065 (three truncated or repeated runs of the second reader); about $0.20 in all |
| Confusion of Atha | one: the plan card showed the request as one long paragraph |
| Atha tries the tool himself | not yet |

**Did the readers catch anything real?** Yes, once each:
- Patch reader: DeepSeek V4.1 Flash 1017 (second) flagged that `_parse_bound` stripped whitespace, so `' 2026-01-01 '` was accepted against the PRD rule. True deviation, minor. Hy4 Flash (first) said ok.
  The patch was rejected and redone. First real-job evidence for the tested pair.
- Domain reader: a fresh Sonnet reading flagged "keep in input order" as writer-only text (harmless in substance) and closed the item; the issue was rewritten without the sentence.

## Frictions found (each is a candidate for T5/T6, in the order met)
1. **The plan card shows the whole request as one paragraph** (newlines lost, 2,358 characters): Atha: "No.1 nya terlalu panjang". Fix: cut with "selengkapnya", keep line breaks (display only).
2. **Issue 1 of a new repo has no runnable example** (module not there yet; the writer says so). The install card is closed by condition (h); (a), (b), (i) do not apply; scope is not compared. `apply` still worked on Atha's word.
3. **The PRD writer cannot run the examples of items 2..n**, so a malformed example is found only when the job starts. Recovery: `prd reply --rebase`, a new folder, a new queue, a new plan approval.
4. **`prd reply` is refused while the old queue is not closed** ("two queues would race for the same HEAD").
5. The agent stored `Transaction.date` as a `datetime.date` while the PRD said text; the rewritten PRD followed the code.
6. About 3 to 5 minutes of machine time per issue, the rest is waiting for a human step.
7. **The example gate did not know the src layout** (it looked for the package in the repository root): every example was refused, whoever wrote it. Fixed in PR #633 (one line, test red on the old code).
8. After a gate fix the queue stays STOPPED until the blocked job is abandoned by hand; a job already `REVIEW_READY` cannot be abandoned.
9. **Examples whose setup imports the standard library (`Decimal`, `date`) are "not showable as numbers"**: condition (h) closes every install card and the domain reader sees no numbers, only the issue text. Needs a card grammar that accepts stdlib imports or objects built from repository classes.
10. **A REJECTED queue item has no retry**: redo = `queue close`, `prd reply --rebase`, a new plan approval, a whole new pipeline for the issue. Candidate: `queue retry ITEM` that makes a new job from the same issue and appends the patch reader's finding verbatim as a labelled addendum (model statement, bounded length, retry limit, money cap), decided by Atha on the card, so the correction comes from Argus and not from Claude.
11. The second patch reader (DeepSeek 1017) was cut at the 12,000-token output limit twice on one patch; `--max-output 30000` fixed it. Consider a higher default or one automatic retry.
12. **The domain reader is stricter than the human gate needs**: a `concerns` on a harmless writer-only phrase blocks `apply` for good. Candidate: `argus apply --accept-domain-concerns "<Atha's reason>"` (recorded in the log and shown on the card), only for the domain reader, not for the patch reader. Atha chose a PRD rewrite this time and kept this as a candidate.
13. The machine's scope mark flagged `README.md` ("not named by the issue") although the issue asked for a README section: the anchors are code names. A false alarm a human can judge, but it will recur.
14. Part of the PRD improvements came from instructions Claude wrote in `prd reply` messages (for example the explicit rule about padded dates); count it as operator help, not as Argus alone. The first PRD (five issues) was written from Atha's request only.

## Web page for ledger-cli (second part, 2026-11-19/20)

Request (Claude's draft, from Atha's wish "report viewable from the phone, HTML only, no JavaScript"): `serve [--port]`, `GET /`, `POST /report`, `POST /report.json`, 404 elsewhere, escape, no upload kept; three ordered issues. Hidden tests: 10 web tests (written before Argus; the hash recorded in `~/ledger_eval/web_hash.txt` could not be re-derived afterwards, but the files are unchanged since 16:57:04 on 2026-11-19, before the first PRD approval, so this is mtime evidence, not hash evidence).

Result: **web 10/10, CLI 12/12 (still), ledger-cli's own 55 tests pass**; three commits on `ledger-cli` main (`a2a3ea2`, `777ee32`, `e9bd633`), not pushed. PRD writer spent $0.10 over five turns (one WRITE_FAILED: output truncated). Issue 1 needed two rejected jobs before the third passed; issues 2 and 3 passed at the first job.

Frictions (continuing the list above):
15. The PRD writer refused `/api/report`: the harness treats `/api/...` as the viewer-proxy side. Renamed `/report.json`.
16. PRD turn truncated (long contract plus three issues): asked for a shorter text.
17. Two patch readers found real defects in issue 1 (unread request body on a kept-alive connection, 501 for other methods, bad Content-Length): rejected twice. The first rejection came from a Claude reader after DeepSeek was truncated. DeepSeek V4.1 Flash 1017 spends 30k to 42k reasoning tokens on a 10k-token patch; the ceiling is now 100,000 and both readers always read (PR #635, #637).
18. `queue retry` (built from this): the second job got both readers' findings verbatim and its tests covered TRACE, keep-alive and Content-Length. First real use worked.
19. **The domain reader found a writer-only detail in every issue**, each time a small, harmless one (JSON indent and utf-8-sig and the "no file uploaded" text; `serve --port abc` exits 2; status 200, `text/html`, `<p class="error">`, `html.escape`; CSS values, class names, the heading "Galat", the README section name). Rewriting the PRD once removed five details and exposed one more. Built `argus examples-accept` (PR #638): a human's written reason, bound to the bundle and both readings, shown on the card and logged on `apply_started`. Atha accepted three times; the reason texts were drafted by Claude and approved by Atha (recorded as such).
20. The domain-reader bundle shows the operator's `prd reply` messages as "the human's words". Candidate: mark operator messages.
21. Graded for the product: the three issues were applied only after both patch readers said ok, the examples passed, and the hidden tests pass. Graded for the process: three human acceptances of domain concerns, none of which found a real defect; the patch readers found the real ones.

## Next
Do not build more gates for this. Candidate builds in the order of pain: a connector that runs the steps and stops only at Atha's gates (T5); `queue retry` (10); card grammar for stdlib setups (9, 2); `apply --accept-domain-concerns` (12); the plan card request display (1); first-issue-of-a-new-repo handling and `argus env init` (T6).
Second project, if Atha wants it: patungan (bill splitter), harder (rounding of leftover Rupiah, minimal settlements).
