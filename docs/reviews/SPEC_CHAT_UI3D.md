# SPEC_CHAT_UI3D — the Draft details page: the existing tests a draft changes, as a diff (rev 0)

Origin: SPEC_CHAT_UI3 phase 3d (PENDING F22). Investigation 2026-11-25: a draft holds the whole new text of every existing test it changes (`content`; an
`append` is joined into it before the draft is written); the old text is the run's frozen copy `runs/<job>-<d>/source/<path>`; `check_report.json` of the same
run holds `changed[path].before`, the sha256 of the intake's bytes. Nothing needs git.

## 1. `GET /api/draft/<job>` (read only, chat actions required)
`Steps.draft_detail(job_id)` returns a dict, or None (a 404) when the job id is not a UI job id, the job directory or the draft is reached through a link, or there
is no DRAFTED stage. It never raises. The draft is found as the draft card finds it (`rj._last_draft`, `draft.json` of its run directory, realpath checked, read
with O_NOFOLLOW, 4 MB). Any state of the job is readable (a draft that was approved or applied too).
Fields: `job`, `draft_sha`, `draft_sha12`, `state`, `writable` (<= 50), `must_pass` (<= 50), `tests_n`, `tests` (<= 5), and from `_summary` (check_report of the same
draft: `plan`, `warnings`, `unverifiable`, `baseline_note`, or `summary_note`). No path of the repository, no config, no key.
Each `tests` entry: `path` (a plain relative path: `[A-Za-z0-9_][A-Za-z0-9_./-]{0,198}`, no `..`; otherwise null and the note "the path is not shown", and nothing is read), `diff`
(`acceptance.changed.unified` of the old text against the new, 400 lines at most, then scrubbed and cut to 60 000 characters), `before_verified` (the sha256 of the old
bytes equals the report's `changed[path].before` AND the report is this draft's), `removed` and `modified` (<= 50 `{node, reason}`, scrubbed, 200 and 500 characters),
`note`. Limits and failure: a new text over 256 KB gets no diff ("the new text is too large to show"); the old file is read with O_NOFOLLOW as a regular file of
at most 256 KB, and neither `source/` nor the file may be a link; any failure of one test is "unavailable" for that test only. A text that looks like a key is withheld by
the scrubber as everywhere else. No new action, no write, no key, no money.

## 2. The page
A button "Draft details" on a queue item whose job is AWAITING_APPROVAL, REVIEW_READY or APPLIED opens the page in the Queue tab (`showDraft`; GET only; text nodes only;
an answer that arrives after the person left the tab draws nothing). Order: the existing tests first (path; the machine's mark "old text matches the recorded hash" or "old
text not verified against a recorded hash"; the diff with its own + and - characters, the two header lines marked as headers by position; the writer's removed and modified
notes labelled "written by a model"), then the folded list of files it may write and the tests it must pass, then the writer's plan, risks, warnings and unproven notes labelled
model text. No button on this page prepares or confirms anything.

## Risks to review
- A link anywhere on the path (job directory, run directory, `draft.json`, `source/`, the old file) must never be followed; nothing outside the job's run directory is read.
- `ch.unified` (difflib) on texts up to 256 KB: time. The route is on the single-threaded server.
- A hostile draft (types, sizes, counts) must give a smaller page or `unavailable`, never a 500.
- The old text is a copy of a file of the repository: the scrubber withholds key-like text; a test file with `token = "` shows as withheld.
- Tests lock JS lines and `STATIC_SHA256`.
