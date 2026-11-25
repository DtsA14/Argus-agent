# SPEC_CHAT_UI3 — the phone chat looks like a workspace: bottom tabs, a side panel by repo (rev 0, for Atha's word)

Origin: Atha 2026-11-25, "tampilan kurang lebih kayak di Claude: bottom nav bar dan hamburger/side panel". Mockup (7 screens, sample data):
https://claude.ai/artifact/SZ7aPNKSBFk6Df9qm8x9JS . Reference picture: `docs/refs/chat_ui_reference_2026-11-17.png`.
This replaces the "merge the viewer into the chat" idea: the viewer stays on 8710, read only, and is linked from the panel.

## What exists today (checked in the code)
`chat_static/index.html` already has a side panel (`#panel`, the ☰ button, the job list) and a row of mode chips (Status, Issue, PRD, Riset,
Keputusan, Kartu) above the composer. Pages exist for issue, research, decision, plan and install cards. So this is a reshaping of
navigation and of one list, not a new app.

## The change, in phases (each its own PR)
**3a. Shell (presentation only).** The mode chips become a bottom bar of four tabs: Obrolan, Antrean, Keputusan (with the count of
what waits for the person), Biaya. The side panel keeps the job list, grouped by repo (collapsible, a badge "N menunggu" on a repo
that has something waiting, a "Tanpa repo" group for jobs without one, a kind tag Kode/PRD/Riset, status on its own line, filters
Semua / Menunggu kamu / Riset), a link "Buka viewer (baca saja)" (navigation only, never `fetch`), today's cost, the person.
Existing endpoints only (`/api/threads`, `/api/decisions`). No new route, no new action.
**3b. Antrean tab.** One card per queue: progress, each item's state, "Buka" for the item that waits. Needs a GET that lists queues
(none exists for the page today; `queue.status` and `queue.status_lines` hold the facts).
**3c. Biaya tab.** Two different numbers, never one: *Terpakai* (spent, from the jobs' own records, `Cards._spent`) and *Dipesan*
(the daily exposure the cap counts: the full cap of every job started via the UI, `Actions.exposure`). The cap meter is the second.
Per job and per kind (Kode, PRD, Riset). A GET that returns both, with unknown cost shown as unknown, never 0.
**3d. Rinci draf.** A read-only page for the draft that waits: machine facts (writable files, required tests, budget), the changed
existing tests (see risk 3), the writer's text folded and labelled model text. One button "Setujui dan jalankan agen" that opens the
same two-step card as today; the approval stays bound to the full draft sha.
**3e. Research report page** in the same style (question, summary labelled model text, claim check from the machine).

## Wording rules kept
Who speaks stays a label (mesin, model, pembaca, atha). Nothing is called verified that the machine did not check. The four-way
"Verified / Inferred / Model / Unverified" scheme was considered and dropped: the machine cannot tell "inferred" from "model-made".
No estimate of how many lines will change before the agent has written anything.

## Risks to review
1. No new POST, no new action; every button is an existing action through prepare and confirm. The viewer link is a plain link.
2. `STATIC_SHA256`, the tests that lock JS lines and the node smoke tests move with every static change; CSP unchanged (no inline).
3. 3d: a draft's `changed_tests` entry holds `content` (whole new file) or `append`; "before" is the base commit's file. Whether the
   chat can show before and after cheaply (the frozen source of the run, read by name, no link) is **not verified yet**; if it cannot,
   the page shows the appended lines or the new content and the removed/modified reasons the draft states, and says what it cannot show.
4. 3b and 3c add GET routes that read job and queue files written by other processes: strict lane (Host check on every method, bounded
   reads, hostile files give "unavailable", never a 500). 3a and the CSS are presentation: advisory lane (tests that fail on the old
   code, precheck, one review).
5. A repo grouping needs the repo of each job: jobs without one (research, old jobs) go to "Tanpa repo"; how many is unknown until built.

## Needs Atha's word before building
The look (the mockup is the proposal), the four tab names, and that 3b to 3e are strict lane with their own review.
Not touched: the manager (`chat:` config), any limit, any model.
