# Plan F47: one chat per topic, a foreman that remembers (Atha 2026-11-28)

Mockup: https://claude.ai/artifact/TqzGfNGUa2bCsUDt7A6fPL (four phone screens). Status: planned, nothing built. Every phase is its own strict-lane PR set (spec, read-only Opus review, mutants once, precheck, verify_at, merge on Atha's word) unless it is display only.

## Goal

Atha runs a whole piece of work (talk, issue, draft, code, read patch, apply) from ONE chat per topic, and the foreman remembers the conversation instead of forgetting after about 4 KB. No 12 hour wall.

## Principles that do not change

- The foreman proposes; it never approves, applies, starts or spends. Every action stays a card Atha reads and confirms.
- Money stays bounded: a session cap, a daily cap ($7), and wherever authority is renewed it is Atha's confirmation.
- Text written by a model (the foreman's replies, a summary of them, a topic title it suggests) is data on the page and in prompts, never an instruction.

## Findings this plan rests on (read from the code, 2026-11-28)

- `manager_job._context` hands the model only the last `summary_bytes` = 4096 bytes of earlier turns; older turns are cut with no summary. The model's real context window is never reached.
- `ttl_hours` (12, at most 23) exists because a session's `max_usd` counts as daily exposure for 24 hours from its creation. It is accounting, not a safety control. The real controls are the money cap and the one confirmation.
- Typical foreman turn on Morph about $0.0003; $0.20 is hundreds of turns, so money is not what stops a chat today: the 40 turn limit, the 12 hour limit and the 4 KB memory are.
- `next_steps` already shows harness sentences for research/PRD jobs; since F44 an issue started from a proposal records its source session in the audit (the link topic to jobs).

## Phases (each live and tried on the phone before the next)

**A. The foreman remembers (context and compaction).** Full history goes to the model up to a token threshold (default proposal 40,000). Near it, the code (not the model) runs one fixed compaction call: a stored summary entry (sha, labelled "written by a model") that the page shows in a fold "Summary so far". Later turns get the summary plus the newest turns verbatim. Fixes cut-off memory; `max_turns` rises with it. Includes F45 (the instruction says to propose `none` for what Argus cannot do) and its re-measure. Measured by a deterministic recall test: N planted facts, compaction, questions scored by code. Size: medium.

**B. Money, not time.** `ttl_hours` goes away. When the session cap is nearly used the page shows a one tap card "Add $0.20" (a new action; the confirmation is the only way authority grows). Exposure is booked per turn from audit lines (as `prd_reply` and the patch readers already are), so the age of a session no longer matters for the daily cap. Most careful phase: the exposure scan, the 24 hour window and the top up refusal at the daily cap each get tests and mutants. Size: large.

**C. Topics.** A topic is a label and a history, with no authority: `topic` (id, title) stored on the foreman job; a list endpoint; the side panel shows Topics on top (title, repo label, status) and the per repo job list below as the archive; New topic; the person types the title (a foreman suggested title comes later and stays text). A session lives inside a topic; continuing a topic after a pause is the same session (phase B) or one confirmation for a new one. Size: medium.

**D. The steps of a topic, in the chat.** `next_steps` grows to issue and code jobs started from the topic's sessions, with the harness's fixed sentences and buttons that only prepare the existing cards: Start (issue_start), Reply, Approve draft (job_approve), Read patch (patch_read_run), Open install card. The chat refreshes itself when a stage ends (this is F41 (a): a banner). Size: medium.

**E. Apply in the chat.** The install card (patch summary, readers, checks) is shown in the topic and its Pasang button prepares the existing `code_apply` card; the final confirmation card stays. No new authority. Size: small to medium.

After E: hide New issue and the other types from the `+` menu (only when the topic flow is proven in use), delete nothing else.

## Decisions for Atha

1. Who types the topic title (default: Atha; the foreman may suggest later).
2. Apply button: prepares the confirmation card (default) or applies on one tap (not recommended: Pasang changes the repo).
3. Defaults to confirm: compaction threshold 40,000 tokens; top up $0.20; keep the per repo list as the archive.

## Not in this plan (still open elsewhere in PENDING)

F32 attachments, F34 issue_reply money, F42 more samples for provider and model choice, B11 e2e, the phone VPN plan.

## Risks, said plainly

- Compaction quality is unproven until phase A's recall test runs; a summary can drop a detail (the newest turns and the whole history stay stored, only the summary replaces older text in the prompt).
- Per turn exposure booking (B) is the hardest part to get exactly right; it gets the longest review.
- The foreman model (DeepSeek Flash 1017) still refuses in plain chat now and then where `none` is expected (F45); not a safety issue, but visible.
