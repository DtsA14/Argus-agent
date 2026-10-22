"""General tasks, slice 1 part B: an agent works on a copy of a repository under a frozen, human-written contract,
and the harness decides the outcome from evidence (acceptance/). See docs/reviews/REVIEW_GENERAL_TASK_1B.md.

  status   run statuses and the only legal transitions between them
  frozen   the contract as frozen at setup; every later node checks it is unchanged
  tools    the agent's tools: list/read/write files inside the workspace scope, run a validation, finish
  agent    one attempt: the tool-calling loop, with the per-step memo and a reservation restored from the ledger
  run      the graph (setup -> attempt -> acceptance -> ...), admission from the ledger, resume
"""
