# SPEC_CHAT_UI2 — who wrote the request, which repositories the writer read (rev 2)

Origin: the first full chat flow (2026-11-25, ledger-cli). PENDING_PRIORITAS F10, F11, F12. F6 is in another repository
(see "Not here").

## Problem
1. F10. The numbers-reader bundle (`router/examples_read.py`) calls every human message in the PRD conversation
   "the human's words, verbatim". After a `prd reply` typed in the terminal (by the human or by a Claude session relaying
   the human's rules; the record cannot tell which) that is a claim the record does not support.
2. F11. The plan card of the chat (`app.js` `renderCard`, line "permintaan") labels the request with the human's colour
   and the word "permintaan" whoever wrote it, and shows it whole (up to REQUEST_MAX).
3. F12. `prd new --ref` freezes `job.data["refs"]` (name, commit, files, README). The plan card never shows them: the
   person approves a plan without seeing which other repositories the writer read.

## Change
A. Provenance of a human message, from what is already recorded, no schema change, no new field the client sends:
   - message 1 of a PRD conversation: `created` log entry with `via == "ui"` -> "typed by the human in chat"; otherwise
     "typed in the terminal (the human or a Claude session; not recorded which)".
   - every later human message of a PRD conversation: always the terminal label (chat has no reply action).
   `approve_cards._plan` already computes `request_by` ("chat" | "tidak_tercatat"); it stays the one source.
B. Bundle (F10): the heading of each request section becomes `DATA request <n of m>: <label> (verbatim)` using the labels
   in A. The template text and the bundle are recorded by hash, so existing readings of old bundles become stale as they
   should (the bundle changed); this is the same effect as any bundle change and needs no migration.
   The reader instruction keeps saying: the numbers rule must come from the request, a repo document or the writer text;
   it adds one sentence: "a request typed in the terminal may be written by a Claude session: it is the operator's
   statement of the human's rules, not the human's own proof".
C. Chat plan card (F11): `Plan.card_facts` passes `request_by` and the (already scrubbed, cut) `request`; the page
   labels it "permintaan (ditulis lewat chat)" or "permintaan (dari terminal: manusia atau sesi Claude, tidak tercatat)"
   and shows at most 400 characters with "dipotong" when longer (the full text stays in the PRD job page). The writer's
   summary stays labelled model text and is shown folded in a `<details>` like the UI-1 block ("Ringkasan penulis (model)").
D. References (F12): `approve_cards._plan` adds `refs: [{name, commit12}]` read from `data["refs"]` only when it is a list of
   at most 3 dicts whose name matches the registered-name shape and whose commit is 40 hex; anything else drops the field
   (never an error). `card_facts` passes it. The page shows one line "Repo rujukan (dibaca penulis, hanya baca): a@abc123, b@def456"
   outside the folded block, because it is a machine fact about what the model saw.

## Not here
F6 ("no draft to review" on the viewer's draft page while the job waits for approval) lives in `~/argus-viewer`
(`src/App.jsx`, the `nodraft` branch). It is a separate repository with its own release, built through Argus issues. It
stays open as its own small issue; the chat card already routes the phone to the right place.

## Risks to review
- Labels must not claim more than the record shows: "chat" only when the created entry says `via ui`.
- `refs` is job data written by the CLI: names and commits are validated by shape, rendered as text nodes only.
- The pinned static page (`STATIC_SHA256`) and tests that lock JS lines change; the bundle template hash changes.
- No new action, no write path, no key, no money.

## Tests
`examples_read`: bundle heading for a chat-created job (message 1) and for a terminal-created job and for a reply, and the
extra reader sentence; `approve_cards`: `refs` present for a good record, dropped for a non-list, over 3, a bad name, a short
commit; `chat_plan.card_facts` carries `request_by` and `refs`; node smoke test: the two labels, the 400-character cut, the
refs line, the folded summary.

## Rev 2: Opus review (GO WITH CHANGES), all nine amendments taken
1. The label says "dimulai lewat chat (tercatat via ui)"; the record only knows `--via ui`, which a terminal can also pass.
   Pasted text is also possible. No claim of authorship beyond that.
2. One helper `request_by(data)` in a new small module `router/request_by.py` -> list of labels, one per human message,
   keyed on the position in `conversation`: used by `approve_cards._plan` and `examples_read.gather`. Message 1 is "chat"
   only when a `created` log entry has `via == "ui"` (not any entry); every other message is "terminal".
3. refs: reuse `prd_refs.valid` and `MAX_REFS` (2, not 3); name must fullmatch `[A-Za-z0-9][A-Za-z0-9._-]{0,63}`, commit
   `fullmatch [0-9a-f]{40}`, bool/non-str refused. Key absent -> no line; key present but bad -> "rujukan tidak terbaca".
4. `request_by`, `request_count` and `refs` are copied in `build_approve` and `build_go` as well as `card_facts` (the
   confirm cards copy field by field). With replies, the card says "pesan pertama; N balasan dari terminal tidak ditampilkan".
5. The 400-character cut is made on the server, by code points, after scrubbing and after dropping format characters;
   `request_cut` says it was cut. The page never slices.
6. Strict lane. Effect on deploy: the bundle changes, so every reading made on the old bundle is stale: `apply` and
   `queue_go` refuse until two new readings exist. Before deploying: list the waiting plans and in-flight queue items
   (`queue` and `prd` listings) and deploy when none has readings that matter, or accept redoing them.
7. The template keeps the source token `permintaan Atha` as the name of the source "the request as recorded" and says so in
   one added sentence (a terminal request may be written by a Claude session: the operator's statement of the human's rules).
8. The bundle heading keeps the index: `DATA request <n> of <m>: <label> (verbatim)`; tests pin the exact strings.
9. A test pins that `prd_reply` is not in `chat_actions.ACTIONS`, so "later messages are terminal" fails loudly if a reply
   action is ever added.
