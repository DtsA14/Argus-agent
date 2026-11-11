# Argus: notes for agents and reviewers

Argus is an agent harness on LangGraph. Its value is in the guarantees below; review changes against them first.
The guarantees hold on every pipeline:

- **Code job** (`scripts/argus.py code`, `router/job.py`): optional research r1 (`codetask/research.py`) → drafter
  (`codetask/drafter.py`) → human approve → code task (`codetask/run.py`: setup → agent → acceptance) → `argus judge`
  (advice) → applied by a human → staging (`argus stage`).
- **Research job** (`scripts/argus.py research`, `router/research.py`): planner p1 → web workers → synthesis s1 →
  claim checker e1 (`research/stages.py`); each stage is its own one-node graph (`research/loop.py`).
- **`graph.py`** (`main.py`, `runner.py`): the M1–M3 demo (orchestrator → parallel workers → synthesize → evaluator on a
  sales report). Not a production path; kept as the reference graph and for the crash-resume and budget tests on it.

How to verify: `bash scripts/verify.sh` (fresh venv, pinned deps, full suite incl. crash-resume
repeats and stress), or `bash scripts/verify_at.sh <commit>`: the same on that commit in its own git worktree, so
this checkout and its `.venv-verify` stay usable meanwhile; the log is copied into `verification/`. Evidence logs are kept in `verification/`. Open work is in `PENDING.md`,
the status of milestones and ADRs in `docs/Reconciliation.md`, review briefs in `docs/reviews/`.

## Code Review Rules

### Budget and money
- Every model call must go through `harness/llm.py` (`LLMCaller.call`). Flag any `.invoke`, `.stream`,
  `.batch` or `build_chat_model` outside `harness/llm.py` / `models/registry.py`.
  Exception, by decision (2026-11-11): `scripts/smoke_models.py`, a manual smoke script that a human runs on purpose; it is not part of any job.
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

### Advisory lane (Atha, 2026-11-11)
A change is **advisory** only if all of these hold: it adds a hint, warning or display for a human; it can never refuse, block, fail or change
a draft, an approval, a verdict, a ledger entry, a budget, a sandbox run, a key or a deployment; it never raises into its caller (any error
returns "no finding"); it reads nothing outside the repository inputs it is given. Advisory changes need a short spec, a test that fails on the
old code and one review; they do not need mutants or a full `verify_at` (run the touched tests). If any condition fails, or a reviewer doubts it,
it is strict-lane. A hint that becomes a gate (refuses, fails or blocks something) is a new strict-lane change.

### Tests
- A new guarantee needs a test that fails when the guarantee is broken (we mutation-check them).
  A test that is skipped (e.g. Docker unavailable) does not count as passing.
