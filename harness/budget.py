from dataclasses import dataclass


@dataclass(frozen=True)
class Budget:
    max_iterations: int
    max_tokens: int
    max_seconds: float
    stagnation_rounds: int
    max_workers: int = 3

    @classmethod
    def from_cfg(cls, d):
        return cls(**d)


def iteration_cost(estimates, max_workers):
    """Worst-case tokens of one full iteration: orchestrator + all workers + synthesize + evaluator."""
    return (
        estimates["orchestrator"]
        + max_workers * estimates["worker"]
        + estimates["synthesize"]
        + estimates["evaluator"]
    )


def next_iteration_blocker(b, *, iteration, tokens_used, elapsed_s, iteration_tokens):
    """Name of the limit that forbids starting another iteration, or None.

    Tokens are checked by reservation: the whole next iteration must fit in what is left,
    so tokens_used can never exceed max_tokens (given nodes stay within their estimates).
    """
    if iteration >= b.max_iterations:
        return "max_iterations"
    if tokens_used + iteration_tokens > b.max_tokens:
        return "max_tokens"
    if elapsed_s >= b.max_seconds:
        return "max_seconds"
    return None
