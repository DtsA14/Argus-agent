# SPEC_CHAT_UI3C — the Cost tab shows two different numbers: what the cap counts and what the jobs recorded (rev 0)

Origin: SPEC_CHAT_UI3 phase 3c (PENDING F21). Until now the tab summed `stages_usd` of the newest 100 jobs and said the daily cap was not shown.

## 1. `GET /api/cap` (read only, chat actions required)
`Actions.cap_status()` returns `{"cap_usd": float|null, "booked_usd": float|null, "unknown": bool}`:
- `cap_usd` is `daily_cap()` (the configured `chat.daily_cap_usd`).
- `booked_usd` is `exposure()`, the same number `check_cap` uses: the full limit of every job a UI action started in the last 24 hours (plus the
  service's own recent confirms), NOT what those jobs spent.
- When the exposure cannot be computed (a `Refusal`, or any other exception such as a RecursionError on a hostile job file) `booked_usd` is null and
  `unknown` is true: never 0. When `daily_cap()` itself fails, both are null and `unknown` is true. The method never raises.
- The answer is kept `WAIT_TTL_S` (20 s) and cleared by every confirm. `exposure()` itself is untouched, so prepare and confirm never see a kept value.
- No new action, no write, no key, no money; the answer carries three numbers and no text or path.

## 2. The Cost tab
Three cards, in this order, never merged:
1. "Booked against the daily cap": "Booked (last 24 hours): $X of $Y", a bar (not drawn when the cap is 0; the value stops at full when over), "Left: $Z" (never negative),
   and the sentence that the cap counts the full limit of every job started from this chat, not what the jobs spent. While the answer is unread: "Loading…";
   unknown or failed: "The daily cap could not be computed right now." (no number).
2. "Recorded in the last 24 hours": from the job list the page already has (`created_at` within 24 hours, an unreadable date is not counted): total, per kind,
   the count of jobs with a stage that has no cost figure ("not counted, not zero"), and a note that a stage still running is not in it yet.
3. "Recorded stage cost" (the newest 100 jobs) and "Per job": as before.
The tab asks `/api/cap` when it opens and on the poll while it is open.

## Risks to review
- `cap_status()` and `waiting()` share `exposure()`: neither may leave state behind; the kept answer must not shadow a live check.
- The Booked number is the cap's own; the Recorded numbers come from job files: the page must not present one as the other.
- Tests lock JS lines and `STATIC_SHA256`.
