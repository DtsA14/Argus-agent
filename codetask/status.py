"""Run statuses of a code task and the only legal transitions.

  RUNNING            setup done, attempts in progress
  DONE               the last verdict passed: every criterion, with evidence
  FAILED_ACCEPTANCE  the run finished its work but the contract is not met: the last verdict failed and no further
                     attempt is allowed (max_iterations, the same failures again, or no budget for another attempt)
  BLOCKED            the run cannot continue without a human: the contract is invalid or changed, the sandbox is
                     unavailable, or the model provider failed. Recoverable or not, it is never a pass, and it is
                     terminal for this run (fix the cause and start a new run)
  FAILED_BUDGET      no attempt could be funded at all, or a model call overspent its reservation (budget_violation)

Every status except RUNNING is terminal. A terminal status never changes, also not on resume.
"""

RUNNING = "RUNNING"
DONE = "DONE"
FAILED_ACCEPTANCE = "FAILED_ACCEPTANCE"
BLOCKED = "BLOCKED"
FAILED_BUDGET = "FAILED_BUDGET"

TERMINAL = {DONE, FAILED_ACCEPTANCE, BLOCKED, FAILED_BUDGET}
STATUSES = TERMINAL | {RUNNING}
LEGAL = {(None, RUNNING), (None, BLOCKED), (None, FAILED_BUDGET), (RUNNING, RUNNING)} | \
        {(RUNNING, t) for t in TERMINAL}

# Why a run is BLOCKED; each needs a human, none is a pass.
# invalid_contract also covers a checkpoint without the tool allowlist frozen at setup: the run's frozen contract
# state is incomplete, so what the agent was allowed cannot be known (a dedicated reason is not worth it yet).
BLOCKED_REASONS = {"invalid_contract", "contract_changed", "sandbox_unavailable", "provider_failed"}


class IllegalTransition(Exception):
    pass


def transition(old, new, blocked_reason=None):
    """The new status, or IllegalTransition. BLOCKED must say why, and only BLOCKED carries a reason."""
    if (old, new) not in LEGAL:
        raise IllegalTransition(f"{old} -> {new} is not a legal transition")
    if (new == BLOCKED) != (blocked_reason is not None):
        raise IllegalTransition(f"{new} with blocked_reason {blocked_reason!r}")
    if blocked_reason is not None and blocked_reason not in BLOCKED_REASONS:
        raise IllegalTransition(f"unknown blocked_reason {blocked_reason!r}")
    return new
