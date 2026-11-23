# SPEC: a gateway 401 or 402 is not charged, like a 429 (2026-11-23)

Status: **decided by Atha ("429 ya", 2026-11-23); built, for review.** Item 2 of `PENDING_PRIORITAS.md`, second half (the first half, showing the HTTP status, is #695). Strict lane: it changes what the ledger books.

## Rule

A call through a gateway model (`kind: gateway`, OpenRouter) that the gateway answers with HTTP **401** (the key was refused), **402** (payment required: the key's credit limit or the account balance is used up) or **429** (rate limited) was refused **before any model ran**. It is booked as nothing: `charged: "none"`, `tokens: 0`, `usd_nano: 0`, `delivery: "received"`, and the reservation is charged 0. Before this change only 429 was free (`SPEC_RATE_LIMIT_RETRY` R3); 401 and 402 were booked at the worst case.

Unchanged: a **direct provider's** 401, 402 and 429 stay worst case; any other gateway status (403, 404, 408, 5xx, a timeout or a dropped connection, which has no status) stays worst case, because the model may have run; 401 and 402 are not retried (non-transient), a 429 keeps its own retry rules.

## Why

NEXUS-lite stage 4, issue 3: the drafter's call was refused with a 402 (the API key's credit limit, not the account balance) and the ledger booked `$0.0645`, the worst case of a call that cost nothing. It was counted in the job's spend, in the queue's money and in the pilot report (as "worst case, probably not billed"). A refusal that happens before any model runs cannot cost anything.

## The risk, named

The ledger is an upper bound on purpose ("Ledger = batas atas", Atha 2026-11-07). If a gateway ever answered 401 or 402 **after** a model had run (not seen; the calls are not streamed and OpenRouter checks the key and the credit before routing), that call would be booked at $0 and the cap would be a little too generous for that one call. The statuses are listed in one constant (`harness/llm.py` `GATEWAY_REFUSED`), so narrowing the rule is one line.

Also: a gateway model with no price (allowed only when `budget.max_usd` is infinite) now records `usd_nano: 0` instead of null on a 401 or 402, as the 429 path already did; that does not conflict with "unknown cost is null, never 0", because this cost is known to be zero.

## Tests

`tests/test_provider_failure_reason.py`: the constant is exactly (401, 402, 429); a gateway 401 and a gateway 402 are charged nothing, not retried, `delivery: received`, the reservation untouched, the cause keeps the status; a gateway 403, 404 and 500 are still worst case; a direct provider's 401 and 402 are still worst case. `tests/test_gateway.py::test_an_empty_balance_is_not_retried` (a gateway 402) now expects `used_nano == 0` (it pinned the old rule). Mutants (run once): the constant loses 401; loses 402; loses 429; the guard `self.gateway is not None` is dropped (a direct provider becomes free); the constant gains 403; the gateway 429 test fails if 429 leaves.
