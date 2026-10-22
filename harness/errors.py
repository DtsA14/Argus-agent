class TransientError(Exception):
    """Retryable failure (network blip, rate limit)."""


class BudgetExceeded(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


class ReservationExhausted(Exception):
    """A request would not fit in what is left of the node's token/USD reservation. Nothing was sent."""


class InputLimitExceeded(ReservationExhausted):
    """A request's input is over the reservation's per-call input limit (max_input). Nothing was sent."""


class LLMCallFailed(Exception):
    """A model call failed permanently, or kept failing after the allowed retries."""


class EstimateExceeded(Exception):
    """A node used more tokens than it reserved; the budget guarantee no longer holds."""


class PlanRejected(Exception):
    """The orchestrator produced a plan the harness will not run (e.g. too many parallel tasks)."""


class PermissionDenied(Exception):
    """A role tried to use a tool outside its allowlist."""
