# SPEC_CHAT_T4A_ACCEPTED — the queue_go gate honours a written acceptance (rev 1)

## Problem
`Plan.go_facts` (chat `queue_go`) lets an item through only when its domain read is `ok` or `tidak_berlaku`.
Apply (`examples_read.chain`) also honours `examples-accept`: a human's written acceptance of two fresh readings
of which at least one says `concerns`. So a queue that apply would accept is refused at the chat's go gate
(seen on the first real flow, 2026-11-25: item 2 had one `ok`, one `concerns`, the concern being a rule only the
writer's text states).

## Change (router/chat_plan.py only)
1. `card_facts`: when an item's read is `concerns` and `examples_read.accepted_for(jobs_dir, job, n)` returns an
   acceptance, the item's read becomes `accepted` and carries the acceptance reason (scrubbed, at most 300 chars).
   Any other read stays as is. `accepted_for` is the same function apply uses, so the rule is not copied.
2. `go_facts`: `accepted` passes the read gate. It does NOT pass for `concerns` without an acceptance, for
   unreadable, or for stale readings (`accepted_for` binds to the current bundle).
3. `flags()`: an accepted item prints "the readers' concerns about the numbers were accepted in writing, they are
   not an ok: <reason>". It is never shown as ok.

## Not changed
No new action, no new write path, no key, no money. The acceptance is made only by the human's CLI
(`examples-accept`); chat cannot write one. The ack and the typed-reason rules are unchanged.

## Risks to review
- An acceptance for another job, item or bundle must not count (binding is inside `accepted_for`).
- A forged or empty `reason` in the acceptance file must not crash the card (empty or non-dict acceptance).
- The accepted text is model-or-human text shown to Atha: scrubbed and labelled.

## Tests (tests/test_chat_plan.py, five)
accepted passes go; concerns without acceptance refused; acceptance of another item refused; flag text says
"not an ok"; card shows `read: accepted` plus the reason.
