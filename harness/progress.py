"""Pure state transitions for the evaluator loop, kept separate so they can be tested exhaustively."""


def update_progress(best_score, stale_rounds, score):
    """Return (best_score, stale_rounds) after one evaluation.

    Strict improvement resets the stale counter; an equal or lower score counts as a stale round.
    """
    if score > best_score:
        return score, 0
    return best_score, stale_rounds + 1


def decide_status(*, passed, budget_blocker, stale_rounds, stagnation_rounds):
    """Return (status, stop_reason). Priority: passed > budget > stagnation > keep going."""
    if passed:
        return "DONE", ""
    if budget_blocker:
        return "FAILED_BUDGET", budget_blocker
    if stale_rounds >= stagnation_rounds:
        return "FAILED_STAGNANT", f"no improvement for {stale_rounds} rounds"
    return "RUNNING", ""
