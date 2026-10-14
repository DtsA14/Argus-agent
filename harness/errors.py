class TransientError(Exception):
    """Retryable failure (network blip, rate limit)."""


class BudgetExceeded(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


class EstimateExceeded(Exception):
    """A node used more tokens than it reserved; the budget guarantee no longer holds."""


class PlanRejected(Exception):
    """The orchestrator produced a plan the harness will not run (e.g. too many parallel tasks)."""


class PermissionDenied(Exception):
    """A role tried to use a tool outside its allowlist."""
