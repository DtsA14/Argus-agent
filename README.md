# Argus

Agent harness: orchestrator / workers / harness controller / evaluator on LangGraph.
Milestone 1 (harness, budget, crash-resume) plus the provider layer.
Nodes are still fake (deterministic); the provider layer is ready for the real ones.

## Run

    pip install -r requirements.txt
    python main.py --scenario fail_then_pass        # pass | fail_then_pass | never_pass | flaky
    python -m pytest -q

Reproducible check from scratch (fresh venv, pinned versions, full suite):

    bash scripts/verify.sh

## Budget guarantees

- **Tokens (hard):** an iteration starts only if its worst-case cost (`token_estimates`,
  orchestrator + `max_workers` workers + synthesize + evaluator) fits in what is left, so
  `tokens_used <= max_tokens` always. A node reporting more than its estimate raises
  `EstimateExceeded`; a plan wider than `max_workers` raises `PlanRejected`.
- **Iterations (hard):** checked before each iteration.
- **Time (soft):** `max_seconds` is the sum of node run times (parallel workers add up),
  checked between iterations only. It does not interrupt a running node.
- **Stagnation:** a score that is equal or lower than the best so far is a stale round;
  `stagnation_rounds` stale rounds in a row stop the run. Status priority: passed > budget > stagnation.
- Every run ends with a `run_end` event and `result.json` carrying `status` and `stop_reason`.

## Crash-resume guarantees

Against a hard crash, "exactly once" is impossible: work can finish and the process can die before
its result is saved. What the harness guarantees (tested, including 50 parallel-worker crashes):

1. The resumed run ends with the same outcome and the same `tokens_used` as an uninterrupted run.
2. A node run whose result was committed to the memo (`result_committed`) is never performed again;
   if LangGraph schedules it again, the memo answers (`memo_hit`).
3. Work is redone only when it had no committed result at the crash: a node still running, or one
   that finished in the short window before its commit. `tokens_spent` in `result.json` (sum of
   `body_done` events) shows that real extra spend; `tokens_used` stays the accounted figure.

Consequence for real tools: anything with side effects (files, messages, payments) must be safe to
run twice for the same `(node, task, iteration)`, e.g. write to a temp file and rename.

Simulate crashes yourself: `python main.py --crash-at worker`, or `--crash-at worker@after_commit`,
then the same command with `--resume`. A fresh run refuses an existing `--run-id`.

## Providers and models

Everything lives in `config.yaml` (`providers`, `roles`, `prices`).

- Set keys as environment variables: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`. Never put keys in files.
- Swap a model for one run: `python main.py --model worker=deepseek:deepseek-flash`
- Swap permanently: edit `roles.<role>.model` in `config.yaml`.
- Add an OpenAI-style provider: add an entry with `kind: openai_compatible` and a `base_url`. No code.
- Add a brand-new kind of provider: `@register_kind("name")` in `models/registry.py`.

## Verify against the real APIs (needs your keys)

    python scripts/smoke_models.py                  # key, model id, chat, tool calling, cost per role
    python scripts/smoke_models.py --list --grep gpt   # which model ids the provider really offers

The OpenAI model id in `config.yaml` is a placeholder: confirm it with `--list` before trusting it.
Prices are public figures from mid-Oct 2026; an empty price means cost shows as n/a.

## Notes

- DeepSeek charges 2x on weekdays 01-04 and 06-10 UTC (08-11 and 13-17 WIB); `models/pricing.py` models this.
- Checkpoints use `durability="sync"` so a hard crash does not lose the last step.
