# Argus: notes for agents and reviewers

Argus is an agent harness (orchestrator → parallel workers → synthesize → evaluator) on LangGraph.
Its value is in the guarantees below; review changes against them first.

How to verify: `bash scripts/verify.sh` (fresh venv, pinned deps, full suite incl. crash-resume
repeats and stress). Evidence logs are kept in `verification/`. Open work is in `PENDING.md`,
the current plan in `docs/MILESTONE2_PLAN.md`, review briefs in `docs/reviews/`.

## Code Review Rules

### Budget and money
- Every model call must go through `harness/llm.py` (`LLMCaller.call`). Flag any `.invoke`, `.stream`,
  `.batch` or `build_chat_model` outside `harness/llm.py` / `models/registry.py`.
- A request must be refused before sending when it does not fit the node's reservation (tokens and USD).
  Flag code paths that can send first and check later.
- Every attempt must reach the ledger (`llm_call_started` before sending, `llm_call` after), and the
  reservation must be charged even when writing the ledger fails. Money is integer nano-dollars.
- Unpriced models must stay refused while `budget.max_usd` is finite. Unknown cost is `null`, never `0`.
- Do not describe heuristic token counts (non-Anthropic) as an absolute financial cap.

### Crash-resume
- A node result committed to the memo (`result_committed`) must never be recomputed or re-bought.
  Work with side effects must be safe to run twice for the same `(node, task, iteration[, step])`.
- Checkpoints use `durability="sync"`. Flag any change back to the default.
- In agent loops, every model reply and tool result is committed before the loop moves on. Step memo
  keys must carry the step's input identity (and a tool step its parent LLM step and tool version).
- A node run's reservation starts from what the ledger says it already spent (`reservation_from_ledger`).

### Plans and tools
- Orchestrator plans are validated by the harness (`nodes/plan.py`), not trusted from the model.
- File tools must stay inside allowed roots; code execution only in the Docker sandbox, never unsandboxed.

### Tests
- A new guarantee needs a test that fails when the guarantee is broken (we mutation-check them).
  A test that is skipped (e.g. Docker unavailable) does not count as passing.
