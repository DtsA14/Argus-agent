import math
from dataclasses import dataclass

from models.registry import ModelRef, price_for


@dataclass(frozen=True)
class Budget:
    max_iterations: int
    max_tokens: int
    max_seconds: float
    stagnation_rounds: int
    max_workers: int = 3
    max_usd: float = math.inf
    allow_unpriced: bool = False

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


def node_usd_estimates(cfg):
    """Worst-case USD per node run: its token estimate, all billed at the dearer of the role model's
    input/output rate, times the peak multiplier. Nodes not listed in `node_roles` make no model calls."""
    est = cfg["token_estimates"]
    out = {node: 0.0 for node in est}
    for node, role in (cfg.get("node_roles") or {}).items():
        ref = ModelRef.parse(cfg["roles"][role]["model"])
        price = price_for(cfg, ref)
        if price is None:
            if not cfg["budget"].get("allow_unpriced", False):
                from models.registry import ConfigError
                raise ConfigError(f"node {node!r} uses {ref} which has no price; add it to 'prices' "
                                  "or set budget.allow_unpriced: true")
            continue
        rate = max(price["input"], price["output"]) * price.get("peak_multiplier", 1) / 1_000_000
        out[node] = est[node] * rate
    return out


def iteration_usd(usd_estimates, max_workers):
    return (
        usd_estimates["orchestrator"]
        + max_workers * usd_estimates["worker"]
        + usd_estimates["synthesize"]
        + usd_estimates["evaluator"]
    )


def next_iteration_blocker(b, *, iteration, tokens_used, elapsed_s, iteration_tokens,
                           usd_used=0.0, iteration_usd=0.0):
    """Name of the limit that forbids starting another iteration, or None.

    Tokens and USD are checked by reservation: the whole next iteration must fit in what is left,
    so neither can exceed its maximum (given nodes stay within their estimates).
    """
    if iteration >= b.max_iterations:
        return "max_iterations"
    if tokens_used + iteration_tokens > b.max_tokens:
        return "max_tokens"
    if usd_used + iteration_usd > b.max_usd + 1e-12:
        return "max_usd"
    if elapsed_s >= b.max_seconds:
        return "max_seconds"
    return None
