# SPEC: summary at the top of a job's detail (F33), light lane

Atha 2026-11-27: "gw cuma buka bekas issue tapi ga nemu ringkasan"; mock of five kinds sent 2026-11-27, "gass" 2026-11-28.

## What
Tapping a job in the side panel shows, above the stage table, three to four labelled rows (Permintaan, Hasil, Pembaca patch, Menunggu kamu)
and folded details. Page only: `router/chat_static/app.js` (+ a few lines of css), no server change, no new route, no action.

## Where the facts come from (existing read-only routes, nothing new)
issue `/api/issues/<id>`; code `/api/approve/code/<id>` (the install card); research `/api/research/<id>`; PRD `/api/approve/prd/<id>`;
manager and anything else: the thread data only. A route that fails or answers `refused`: one line "Ringkasan tidak tersedia" and the
stage table below stays. The sentences are composed by a pure function `summaryRows(job, facts)` from those fields (counts, states, the
card's checks), never by a model. Free text (the request, an issue's first line, a reason) is cut and drawn with `textContent` only.

## Rules of honesty
- A reader's `ok` is written "Dibaca oleh model, bukan bukti". Concerns, one reading, none, stale, error are written as what they are.
- An installed job says what Argus does not know: push, merge, deploy (G5).
- A closed install card says which check is false (the first `ok === false` label). A card that is open says only that it is open.
- Counts a route does not give are not invented; a missing field removes its row instead of showing a guess.
- The only button is "Buka kartu pasang" for a code job in REVIEW_READY (navigation, as #781). No prepare, no confirm.

## Tests / mutants
Node smoke on the real `summaryRows` and `summaryBlock` with a tiny DOM (five kinds, fallback, odd values); mutants on the rules above.
Pins repinned with `scripts/repin.py`. Light lane: precheck, no `verify_at`.
