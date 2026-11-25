# SPEC_CHAT_UI1 — the chat reads the image pins; the draft card shows what the person approves (rev 1)

Origin: the first full chat flow (2026-11-25, ledger-cli). PENDING_PRIORITAS F16 and F17.

## F16. The chat does not read `.sandbox_image_<env>`
`approve_draft.sandbox_cfg` (CLI) puts `.sandbox_image_<name>` into `ARGUS_SANDBOX_IMAGE_<NAME>` when the variable is
not set. The chat never does, so `Steps.build_approve` calls `rj.environment_changed(job, cfg)` with no image and
refuses ("has no image"). Tests did not catch it because they fake the environment.

Change:
1. `tools/sandbox.py` `load_image_pins(cfg_sandbox, root)`: for each configured environment name, if the variable is
   unset (or was set by this function earlier) and the file exists, set the variable from the file (stripped, one
   line, must look like `sha256:<64 hex>` or be left unset). A variable that the real environment holds is never
   overwritten. The names this function set are kept in a module set so a later call refreshes them from the file
   (an image rebuilt after the chat started is seen, so the chat refuses a job pinned to the old one, as the CLI would).
2. `approve_draft.sandbox_cfg` calls it (same behaviour as before, one implementation).
3. `Steps.build_approve` and `Steps.build_step` call it before any `environment_pin`/`environment_changed`.
No new action, no new write path, no key, no money.

## F17. The draft card shows plan, tests and the writer's notes
The card for `draft_approve` today shows the item text, the draft sha, writable files, validations, cost. It does not
show the plan, the risks, the warnings, the writer's "unverifiable" notes, or which tests change.

Change (card of `draft_approve` only; the card is built from the same `draft.json` whose sha it shows):
- `plan` {files, steps, risks}, `warnings`, `unverifiable`, `must_pass` (test ids of the validations, at most 40),
  `changed_tests` (paths only) and `changed_tests_n`. Built with `router.stage_data.draft_summary(draft, report, stage)`
  where it fits and with the draft itself otherwise; every string passes `scrub`, a length cut and a count cut.
- `check_report.json` is read as a regular file (`_read_file`); if it is missing, unreadable, or its `draft_sha256`
  differs from the draft's, the card carries `summary_note: "summary unavailable"` and none of these fields. The
  approve button stays (the draft sha and the existing fields are unchanged) — the card says so.
- All of these are model text. The page shows them in a collapsed block labelled "Teks penulis (model), bukan bukti",
  and a non-empty `changed_tests` shows a one-line warning outside the block: "Draf ini mengubah tes yang sudah ada".
- The confirm re-derives the draft sha as today; no new field is part of what the client sends.

## Risks to review
- A symlinked or oversized `check_report.json`; a draft with hostile strings (keys, markup): scrub and bounds.
- `load_image_pins`: a pin file with junk (not a digest) must not be exported; never override a real variable; no
  state leaks between tests (module set).
- The static page is pinned by sha256 (`STATIC_SHA256`); update it and the tests that lock JS lines.

## Tests
Real pin files in a tmp root (not a fake of the environment); refresh after a rebuilt file; junk file ignored; real
variable wins. Card fields present for a good draft; absent with a note for a missing, linked, huge or mismatched
`check_report.json`; hostile strings scrubbed; counts cut; the page shows the label and the warning for changed
tests (node smoke test).
