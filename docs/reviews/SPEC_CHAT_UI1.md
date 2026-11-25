# SPEC_CHAT_UI1 — the chat reads the image pins; the draft card shows what the person approves (rev 1)

Origin: the first full chat flow (2026-11-25, ledger-cli). PENDING_PRIORITAS F16 and F17.

## F16. The chat does not read `.sandbox_image_<env>`
`approve_draft.sandbox_cfg` (CLI) puts `.sandbox_image_<name>` into `ARGUS_SANDBOX_IMAGE_<NAME>` when the variable is
not set. The chat never does, so `Steps.build_approve` calls `rj.environment_changed(job, cfg)` with no image and
refuses ("has no image"). Tests did not catch it because they fake the environment.

Change (rev 2, Opus review amendments 1, 3, 4: the chat never writes `os.environ`, because the spawned CLI inherits
the process environment and would then treat a chat-derived value as a real variable):
1. `tools/sandbox.py` `pinned_image(cfg_sandbox, name, root)` -> `(image, problem)`, a pure lookup: unknown name ->
   the existing problem; the variable `ARGUS_SANDBOX_IMAGE_<NAME>` if set; else the file `<root>/.sandbox_image_<name>`
   if it exists (opened O_NOFOLLOW, regular file, at most 300 bytes, one line, must be `sha256:<64 hex>` or
   `<name>@sha256:<64 hex>`; anything else is a problem "the pin file of <name> is unreadable", never a fallback);
   else the configured image. The order (variable, file, configured) is what the CLI has after `sandbox_cfg`.
2. `router/job.py` `environment_pin` uses `pinned_image` (root = its `root` or ROOT). `environment_changed` follows.
   `sandbox_cfg` and `tool_version` are not changed.
3. `Steps.build_step` calls neither `environment_pin` nor `environment_changed`: not touched. Only `build_approve` is
   fixed by (2).
No new action, no new write path, no key, no money, no environment writes.

## F17. The draft card shows plan, tests and the writer's notes
The card for `draft_approve` today shows the item text, the draft sha, writable files, validations, cost. It does not
show the plan, the risks, the warnings, the writer's "unverifiable" notes, or which tests change.

Change (card of `draft_approve` only; the card is built from the same `draft.json` whose sha it shows):
- `changed_tests` come from `draft["changed_tests"][*].path` (type-checked strings, at most 40); `must_pass` from the
  validations (at most 40 ids); `red` is left out; with no `baseline` the card says "no baseline recorded".
  `_has_key` is applied to the whole summary as well as `scrub` per string (a hit drops the summary with a note).
- `plan` {files, steps, risks}, `warnings`, `unverifiable`, `must_pass` (test ids of the validations, at most 40),
  `changed_tests` (paths only) and `changed_tests_n`. Built with `router.stage_data.draft_summary(draft, report, stage)`
  where it fits and with the draft itself otherwise; every string passes `scrub`, a length cut and a count cut.
- `check_report.json` is read from the same verified run directory as the draft, with `_read_file` and a 1 MB limit; it must
  be a dict whose `draft_sha256` equals the draft's. The summary is computed in its own `try` with a broad `except`
  (a hostile baseline must not turn the card into a 409): on any failure the card carries `summary_note: "summary unavailable"` and none of these fields. The
  approve button stays (the draft sha and the existing fields are unchanged) — the card says so.
- All of these are model text. The page shows them in a collapsed block labelled "Teks penulis (model), bukan bukti",
  and a non-empty `changed_tests` shows a one-line warning outside the block: "Draf ini mengubah tes yang sudah ada".
- The confirm re-derives the draft sha as today; no new field is part of what the client sends.

## Risks to review
- A symlinked or oversized `check_report.json`; a draft with hostile strings (keys, markup): scrub and bounds.
- `pinned_image`: a pin file with junk (not a digest) is refused, never a fallback; the variable wins; nothing is
  written to the environment, so nothing leaks into the spawned CLI or between tests.
- The static page is pinned by sha256 (`STATIC_SHA256`); update it and the tests that lock JS lines.

## Tests
`pinned_image` with real pin files in a tmp root (no fake of the environment): variable wins, file, configured
fallback, junk file refused, symlink refused, oversized refused, `<name>@sha256:` accepted; a file rebuilt between
prepare and confirm changes the answer; a spawn test: the child's environment carries no chat-derived pin; a hostile
baseline still leaves the button (also in `state()`). Card fields present for a good draft; absent with a note for a missing, linked, huge or mismatched
`check_report.json`; hostile strings scrubbed; counts cut; the page shows the label and the warning for changed
tests (node smoke test).
