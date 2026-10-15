"""Acceptance for general tasks (docs/reviews/ACCEPTANCE_GENERAL.md): a human-written contract, frozen before the
agent runs, and a verdict the harness reaches from evidence on disk and in the sandbox, never from the agent's claims.

  contract    load, validate and freeze a contract (the agent can never change or loosen it)
  workspace   copy the input repository, snapshot it, and check what changed against the contract's scope
  validation  structured validation commands (allowlisted argv, no shell) run in the sandbox, and their results
  claims      SUMMARY.json: the agent's structured claims, each checked against the harness's own evidence
  verdict     every criterion with its evidence, and the outcome: pass, fail or blocked
"""
