# SPEC: a human's written acceptance of the domain reader's concerns

Why: in the ledger-cli web pilot the domain reader (two Claude sessions) closed condition (i) over rules only the PRD writer states (indent, utf-8-sig,
then `serve --port abc` exits 2). Each rewrite of the PRD costs a round and the next reader finds the next writer-only detail. The patch itself was `ok` by
both patch readers and the examples passed. The human needs a written way to say "I accept this concern" without opening anything else.

What it is:
- `argus examples-accept <prd job> --item N --show` prints the fresh `concerns` notes of the item and two shas: the bundle sha and the concerns sha
  (`concerns_digest`: sha256 of both readings of the item, whole entries with their slots, in a fixed order, so sources and verdicts count too). Both readings are printed.
- `... --reason "<words>" --bundle-sha B --concerns-sha C` writes `examples_accept_<turn>.json` in the PRD job directory (atomic, no symlink followed,
  a damaged file is refused, never replaced). Refused unless: BOTH readings of the item are there, valid, fresh, by two different reader ids, with at least one `concerns` (the concerns of one reader alone are not accepted), B is the bundle sha now, C is the concerns
  digest now, the reason is non-empty text (cleaned, at most 500).
- `examples_read.chain` (the one place `apply` and the install card use) returns `ok` with kind `accepted` when its kind is `concerns` and an acceptance holds
  for this very bundle sha and this very concerns digest. Anything unexpected (damaged file, bad shape, other digest) is not accepted: the gate never opens
  by accident. `status()` itself is unchanged: the note stays `concerns`.
- The install card's condition (i) is ok with the text "keberatan pembaca angka diterima secara tertulis (bukan ok dari pembaca): <reason>".

What it is not: not for the patch reader (`patch_read` is untouched; `apply` still needs two `ok` patch readings), not for a stale, missing or single
note, not a change of any reader's verdict, no new log kind. The record cannot tell the human from a Claude session (label `ACCEPT_LABEL`), like every note.
It stops holding when the bundle changes (documents, examples, folder, template) or when any concerns entry changes.

The log: `apply_started` carries `domain_gate: accepted`, `domain_accept_at` and `domain_accept_reason` (the acceptance file can be replaced later; the log cannot).
