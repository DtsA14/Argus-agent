# Backlog

Carried from the milestone 1 audits (GPT review, 2026-10-14). Each item names the milestone where it must be closed.

## Milestone 2 (real workers, tools, sandbox), blocking

- **[Ditutup di 2a]** **Per-request token cap for real LLMs.** `EstimateExceeded` is detected after a call returns, so the money is
  already spent. Before any real provider call:
  - set the request's `max_tokens` (output) from the node's remaining reservation;
  - measure input tokens before sending (or cap the prompt) so input + output stays within the estimate;
  - count usage of every attempt, including failed attempts and retries, not only the returned result.
    Today `guard` only adds `tokens_used` from the successful attempt.
- **[Ditutup di 2d]** **File access is not a sandbox yet.** `ToolGate` limits tool names per role, but `tools/registry.write_file()`
  accepts any path (verified: `../escaped.txt` writes outside the run directory). Resolve the path, then require it
  to stay inside an allowed root (the run directory); reject symlinks that point outside. Same rule for any read tool.

- **Side-effect tools must be idempotent.** Resume is at-least-once (see README): a node with no committed
  result at the crash runs again. Real tools that write files or call external services need an idempotency
  key `(run, node, task, iteration)` or write-to-temp-then-rename.

## Milestone 3 (evaluator)

- Recommendations are checked by a regex stub (`recs_rubric`), not a rubric. Replace with the LLM rubric and keep
  the programmatic checks as the gate.
- Fixed early: extra months that are not in the data now fail (`trend_no_extra_months`).
  Still to review: duplicate lines, wrong ordering, and a report that has extra sections or products.

## Known limitations (accepted for now)

- `max_seconds` is a soft limit: summed node time (parallel workers add up), checked between iterations.
