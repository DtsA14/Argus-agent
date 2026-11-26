# Spec CHAT-MANAGER P1 (rev 0): the `manager` job, `argus manager`, the session action and the turn route (no UI)

Parent: `SPEC_CHAT_MANAGER.md` rev 1 (section 13 is binding; the order is P2a done, P0 done, now P1). Atha 2026-11-26: "Manajer chat bro"; K1 yes ($0.20 a session, $0.03 a turn, inside the $7.00 daily cap; this amends SPEC_CHAT_APP 11.5 and the chat rule of AGENTS.md); model `openrouter:deepseek/deepseek-v4.1-flash-1017` for talk (K3); `chat.manager` may be added to config.yaml; `readable_repos` stays empty (K2). Strict lane. P1 has no page: it ends at routes that tests and `curl` can drive; the page is P3.

## 1. What P1 delivers

1. Job kind `manager` (`router/manager_job.py`): one job = one session = one confirmation; `max_usd` is fixed at creation and never topped up (13.1).
2. CLI `argus manager new|turn|status` (`scripts/argus.py`).
3. Chat actions: `manager_new` (card, `prepare`/`confirm`, the one confirmation of the session) and the turn route `POST /api/manager/turn` (13.4); read route `GET /api/manager/<job>`.
4. Exposure: a manager job created via `ui` counts its `max_usd` for 24 h (13.2).
5. Config: `chat.manager` and one role `manager`.
6. Registration of the kind in `router/job.py` (13.11).

Out of scope: the page (P3), proposals turned into `prepare` fields (P2b), the next-step card (P4), the `plan_model` slot (no P1 code needs it: P4 adds it with its own per-slot cap, 13.13).

## 2. Config

```yaml
chat:
  daily_cap_usd: 7.00
  manager:
    role: manager              # one role for talk (P1); `plan_model` comes with P4
    session_cap_usd: 0.20      # the job's max_usd; the card shows it (K1)
    turn_cap_usd: 0.03         # worst case of one model call, reserved before the call
    max_output_tokens: 1500
    ttl_hours: 12              # below the 24 h exposure window (13.1)
    message_max: 2000
    summary_bytes: 4096        # earlier turns carried into a turn, cut by code
    readable_repos: []         # K2: no repo content reaches the model
roles:
  manager: {model: "openrouter:deepseek/deepseek-v4.1-flash-1017", max_output_tokens: 1500, timeout_s: 120, ...same other keys as roles.issue_writer}
```

`router/config` validation (where `chat.daily_cap_usd` is read) accepts the block; every number is finite and positive, `turn_cap_usd <= session_cap_usd`, `ttl_hours <= 23`, `readable_repos` is a list (an entry must be a registered repo; empty in P1 and any non-empty value is refused until P1b reads repos). The chat never reads `chat.manager` for anything but these keys.
Because the config changes: grep the tests that derive from config.yaml (`test_budget_experiment`, `tests/test_chat_cap*`, role listings) and run them before `verify_at`.

## 3. The job (`router/manager_job.py`)

States: `NEW -> OPEN -> ABANDONED`, `NEW|OPEN -> BLOCKED`, `BLOCKED -> ABANDONED`, `NEW -> ABANDONED`. `LEGAL` is registered in `Job.move` next to the other kinds. The job file (written with `scrub_value` like the others):
`{"job", "kind": "manager", "state", "created_at", "max_usd": session_cap, "inputs": {"role", "model", "readable_repos": []}, "conversation": [{"from": "human"|"manager", "at", "text", "propose"?, "usd"?, "call"?}], "stages": {}, "log": []}`; the ledger is `<job dir>/manager_ledger.jsonl` (an `EventLog`, as `env_propose`).

`new(cfg, deps, jobs_dir, job_id, via)`: `via` must be `ui` when given and then `job_id` must pass `research.ui_job_id_problem` (the exact harness shape and window); creates the job `OPEN` with `note(created, via=...)`. Money: `rj.live(...)` confirmation text states model, caps, "your messages and the model's replies go to the model provider (OpenRouter -> DeepSeek) and may be kept by it; no repo content is sent", "the manager cannot approve, apply, merge or confirm anything".

`turn(job_id, message, cfg, deps, models=None)` under `job.lock()` (busy -> `JobBusy`):
1. Refuse (nothing recorded, exit non-zero) when: kind is not `manager`; no `created via ui`; state is not `OPEN`; `deps.clock() - created_at > ttl_hours` (the job moves to `BLOCKED` with reason `expired`); the message fails `message_problem` (empty, longer than `message_max`, or `manager_route._clean(message) != message`, i.e. a control, line-separator or format character); the job's ledger spend plus `worst_usd(call)` exceeds `max_usd` (message "the session budget cannot fund another turn"; state unchanged) or `worst_usd(call) > turn_cap_usd`.
2. Record the human message in `conversation` and save BEFORE the call.
3. Build the prompt with `manager_route.system_prompt(repos)` (repos = the registered `issue_writer.repos` names) and `manager_route.user_prompt(message, context)`; `context` is the earlier turns as labelled data cut by code to `summary_bytes` (newest kept; the model's earlier `say` and `propose` are data, never instructions). No repo content, no research text.
4. One `LLMCaller.call` with a reservation (`tr.reservation`, worst case). A failed call or `ReservationExhausted` records a manager entry `{"say": "", "error": <class name>, "usd": billed}`, no proposal, and the state stays `OPEN`.
5. `parse_turn` then `proposal_problems(turn, repos)`. On a problem: ONE retry in the same turn with the problem named (the second call is reserved against the remaining budget; if it does not fit, skip it). After the second failure the turn becomes `say = <fixed text: "I could not form a usable proposal; please rephrase">`, `propose = {"route": "none", ...}` is NOT invented: `propose` is null. Both calls are in the ledger.
6. Append the manager entry `{"from": "manager", "say", "propose" (validated or null), "usd", "calls": n}` and save. The audit trail stays in the job; the chat's audit file gets one line per turn (section 5).

There is no resume: a crash after the call and before the save leaves the human message recorded, no manager entry, and the money in the ledger; `spent` is always read from the ledger, never from the conversation, so the session budget counts it; the next turn is a new call on a new message (nothing is bought twice for the same message because a replay is not offered). `argus resume` on this kind refuses with a sentence. `argus abandon` works (moves to `ABANDONED`).

## 4. The CLI

- `argus manager new --via ui --job-id J --yes` / without `--via` (terminal) `--yes` or the typed confirmation.
- `argus manager turn JOB --message-file F --via ui --key-file K --yes`: the message only by file (never argv), `--key-file` in the provider-prefixed forms the guard allows; the CLI re-checks every rule of section 3 under the job lock (the route's checks are not trusted).
- `argus manager status JOB`: state, spent, turns, ttl left; never prints the conversation text beyond the last `say` (200 characters, scrubbed).

## 5. The chat

- Action `manager_new`: `prepare` builds a card from live data (model, caps, "sessions are confirmed once", data-out sentence of 3) and the digest as every other card; `confirm` starts `argus manager new --via ui --job-id <chat-made id> --yes`. It counts `session_cap_usd` as exposure from the confirm (`exposure_of`), and joins the audit net (`audited_jobs`). `execute` stays an explicit dispatch table (13.9).
- Route `POST /api/manager/turn {session, message}`: all F3 gates (Host, Origin, Fetch-Metadata, JSON only, strict key), message <= 2000 characters and no C*/Zl/Zp characters (written to a 0600 file in the job dir and removed after); the job must be `kind manager`, `created via ui`, `OPEN`, not expired, not busy, remaining budget >= `turn_cap_usd`; ONE audit line BEFORE the spawn with no text (`{"action": "manager_turn", "job", "at"}`); argv is exactly `argus manager turn JOB --message-file F --via ui --key-file K --yes` (key slot `ARGUS_CHAT_MANAGER_KEY_FILE`, falling back to the writer slot); no other argv is ever built from this route.
- `GET /api/manager/<job>`: the conversation (human and manager entries, proposals as untrusted data with `source: "manager"`), state, spent, budget left, expiry; `a is not None`-gated like the other reads; never in the public snapshot.
- A proposal is only data in the job: nothing in P1 turns it into `prepare` (P2b). No model output reaches `confirm` or a token.

## 6. Registration (13.11)

`router/job.py`: `LEGAL` branch in `move`; `status` branch; `resume` refusal; `abandon` allowed (no prd-style marks); the public snapshot and `cards.listing` show a manager job as `{id, kind: "manager", state}` and a fixed title "Manager session", never the conversation; `decision()` names the job only; viewer code that switches on kind falls to its default for `manager` (test with a manager job in the jobs dir: the viewer renders without error).

## 7. Required tests (a break of the guarantee must fail one)

Model never holds `confirm` or a token (grep-style test on the route code and an explicit argv test); the route refuses: non-ui job, expired, busy, remaining < turn cap, foreign Origin, same-site, GET, bad JSON, long or C*-character message; one audit line before the spawn and no text in it; the argv is exactly the fixed form; the CLI refuses the same cases without the route; a turn whose worst case does not fit is not started and costs 0; a crash between call and save keeps the spend (ledger) and the human message and no manager entry, and the next turn does not re-buy; a failed call leaves the job OPEN with an error entry; proposals: outside the menu, extra keys, fenced or doubled JSON, a repo outside `issue_writer.repos` are refused, one retry, then `propose: null` with two ledger calls; injection text in a prior `say` or in the message cannot change the route list or the argv; exposure counts a manager job created via `ui` (also one started from the terminal with `--via ui`), counts nothing after 24 h, two `manager_new` confirms in a row cross the daily cap; the job is never in the public snapshot and the viewer tolerates it; `readable_repos` non-empty is refused; no repo or research text is in any prompt (prompt capture); config limits as above; `execute` of an unknown action is an error, never `issue start`.

## 8. Mutants (to run once after the code review; list to be written with the code, target 20)

Route skips the expiry check; skips the via check; skips the budget check; writes the audit line after the spawn; puts the message in argv; message file kept; ledger not read for `spent` (conversation instead); human message recorded after the call; retry unbounded; second failure invents a route; `readable_repos` ignored; exposure ignores `manager`; exposure counts past 24 h; `manager_new` not in the audit net; unknown action falls to `issue start`; manager conversation in the snapshot; `ttl_hours` not clamped; `turn_cap` not checked; context not cut; model `say` rendered as an instruction (prompt capture shows it outside the data frame).

## 9. Not yet checked (honest)

Whether `LLMCaller` + `tr.reservation` with a one-shot JSON reply behave as in `route_eval` for a multi-turn context (same code path, longer input); how the viewer and `cards.listing` treat an unknown kind today (to be read before the code, section 6 may need more branches); whether `rj.live` can show the session card with only the role (it takes `roles`); the exact key-slot plumbing in `chat_actions.key_file`.

## 10. Amendments from the Opus review (2026-11-26, GO WITH CHANGES; binding, they replace sections 1-9 where they differ)

1. **Ledger = a stage.** One stage `m1 {kind: "manager", run_id: "<job>-m1", cap_usd: session_cap, started_at}` per session; every model call of the session writes its ledger at `runs/<job>-m1/events.jsonl` (what `rj.spent_nano`, `left_usd`, `ChatActions._spent` and the snapshot read). `manager_ledger.jsonl` is dropped. A turn stops (no further call, no retry) when `usd_complete` is false, as `route_eval` does.
2. **`manager new` takes no key and does not call `rj.live`.** It exists only with `--via ui --yes` (a terminal `manager new` is dropped; the chat's `confirm` is its one confirmation). `turn` takes `--key-file`.
3. **Message check:** `mr._clean(m)` is a bool: valid = `m == m.strip()`-free of nothing else than `message_max`, non-empty, `mr._clean(m)` true and no character of category Zl or Zp (`unicodedata`); the same function in the CLI and the route; tests: U+2028 refused, a plain message accepted.
4. **Frame escape:** `user_prompt` neutralises any closing/opening frame tag (`</user_message>`, `</context>`, case-insensitive, also with spaces) in the message and in every context item before building the prompt; prompt-capture tests with the tag in the message and in an earlier `say`.
5. **Size bound:** `max_turns` 40 per session (config `chat.manager.max_turns`), refused before the call; the conversation text kept per entry is cut to `message_max`/`SAY_MAX`; a test shows `_exposure_scan` never reaches the 4 MB limit because of a manager job.
6. **Exposure and naming:** the action is `manager_new` everywhere (parent 13.2's `manager_session` is renamed). `_exposure_scan` gets a `manager` branch (`max(max_usd, session_cap)`, from `created` with `via: ui`, within 24 h, same as prd); `manager_cap()` read once; `("manager_new", mcap)` in the `audited_jobs` loop; `exposure_of` knows `manager_new` (a turn adds 0); `execute` adds a `pending` entry; the audit net covers it.
7. **Code facts:** there is no `router/config` validator: `chat.manager` is validated in `manager_job.settings(cfg)` (called by `new`, `turn` and the chat) with the checks of section 2. `chat.py` gets `POST /api/manager/turn` in `POST_ROUTES` with its own handler (tests that assert exactly two POST routes are updated and say why). `key_file` gets a `manager` parameter (slot `ARGUS_CHAT_MANAGER_KEY_FILE`, falling back to the writer slot) and the route refuses with the `_need_key` message when none is set. The message file comes from `Spawner.message_file` (state dir, 0600, removed on reap), never the job dir. `new()` is keyword-only like `prd_job.new`.
8. **Snapshot:** a manager job is published like every job by `project_job` (`{job, kind, state, created_at, max_usd}`, no title, no conversation); its `log` entries use only `what` values in `LOG_WHAT`; a test with a manager job in the jobs dir shows the snapshot keeps it and leaks no text. `cards.listing` skips the kind (no row in P1). Section 5's and 6's contradicting lines are void. "Nothing recorded" on refusal does not apply to expiry: the expiry refusal moves the job to `BLOCKED`.
9. **Turn details:** `mr.sheet_ok()` is checked before the call (a changed sheet refuses the turn); a truncated reply (`is_truncated`) counts as a problem (retry once); the call is priced with `rj.stage_config(cfg, remaining)` so `LLMCaller`'s own budget also caps; one turn can cost up to two `turn_cap_usd` (the retry), stated in the card; the CLI prints no model text (the spawner's last line reaches the page): only `turn N done, $x` or the refusal sentence.
10. **job.py:** `status` gets a `manager` branch (no `inputs.repo` read); `decision()` treats `manager` like `("issue", "prd")` (name only, no abandon row); `job_abandon` from the chat on a manager job is allowed on purpose (it only closes the session); `resume`, `approve`, `retry`, `redraft`, `reject`, `applied` refuse by state: one test per command proves it.
11. **Process:** this PR also amends in writing SPEC_CHAT_APP 1.3, 7 and 11.5 and the chat rule of AGENTS.md (which flags a chat route that spends without prepare/confirm) with the turn route and its limits (K1).
12. **Extra tests:** the session's spend appears in `list`, `status` and the chat's remaining; `manager new` spawned from the chat succeeds without a key; `argus status` on a manager job does not crash; `decision()` shows only the name; the unknown-action test covers `manager_new`.

## 11. Amendment by P4b (2026-11-26)

The turn argv of sections 5 and 10.3 has two shapes with P4b: the one above, and the same with `--jobs-file G` between `--message-file F` and `--via ui` when the session started jobs (`SPEC_CHAT_MANAGER_P4B.md` sections 2 and 3). No other argv is ever built; the text of a message is still never in it.
