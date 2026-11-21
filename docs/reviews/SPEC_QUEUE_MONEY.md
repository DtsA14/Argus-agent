# SPEC_QUEUE_MONEY (rev 0, 2026-11-21)

Strict lane: the rule of a queue's money (`router/queue.py`, its mirror in `router/cards.py`) and the STOPPED card.

## 1. Problem (pilot ledger-browser, 2026-11-20)
A 3-issue queue with $5.00 stopped at issue 3: "money leaves $0.9769, one job needs $1.00", after two issues were applied and
two retries ran. The real cost of everything was about $0.10. Two causes: an `APPLIED` job holds its whole cap ($1.00) because
a later `argus judge` could still spend on it; the STOPPED card tells the human nothing to do (the steps are terminal
commands the chat does not show).

## 2. Decision
A. The STOPPED card says what is the next step, in words, for each cause (money, REJECTED with or without retries left, HEAD
   moved, BLOCKED), as the CLI's `derive` already knows it (`actions`), without a button.
B. `APPLIED` joins `SPENT_ONLY`: an applied job holds what it spent, like a retired (REJECTED) attempt, whose comment already
   says a later judge "is a separate act of the human with the job's own cap". `retired_nano` and `committed_nano` in
   `queue.py` and `_committed` in `cards.py` move together and a test pins that both give the same number.
C. (the "continue the remaining issues" button) NOT built here: with B the stop on money is rare, and the remaining cases need a
   terminal anyway. Revisit after the next stop in real use.

## 3. Rules
1. B changes only the count. `QUEUE_MAX_USD` ($5.00), the per-job cap and `step`'s refusal when one job does not fit stay.
2. A judge run on an APPLIED job is outside the queue's money (its own cap, the human's act); `argus judge` is not changed and
   still prints its own cap. The old test "a judge on an APPLIED item does not exceed max_usd" is replaced by one that says the
   queue does not count it.
3. A's text is data from `derive`, scrubbed and cut like the card's other lines; no new route, no new action.
4. Nothing reads the ledger in the chat (as today): the number is `job.json`'s recorded stage spend; an unknown cost counts as
   the cap.

## 4. Tests
`tests/test_queue.py`: pure money function (APPLIED counts spent, REJECTED/ABANDONED/BLOCKED/REVIEW_INVALID as before, a still
running job its cap, exactly at the limit, nano); the 3-issue scenario of the pilot now steps to the third issue; a judge after
apply does not change the queue's remaining money. `tests/test_cards.py`: the card's count equals `queue.py`'s on the same
jobs; the STOPPED card shows the next-step line for each cause. Mutants list written, run once after review.
