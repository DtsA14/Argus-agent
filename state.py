import operator
from typing import Annotated, TypedDict


def merge_dict(a, b):
    return {**(a or {}), **(b or {})}


class State(TypedDict, total=False):
    goal: str
    scenario: str          # fake-worker behaviour: pass | fail_then_pass | never_pass | flaky
    run_id: str
    spec: dict             # task list + acceptance criteria made by the orchestrator
    results: Annotated[dict, merge_dict]   # task_id -> worker output
    verdict: dict          # last evaluator verdict
    iteration: int         # number of completed evaluations
    best_score: float
    stale_rounds: int
    tokens_used: Annotated[int, operator.add]
    elapsed_s: Annotated[float, operator.add]
    status: str            # RUNNING | DONE | FAILED_BUDGET | FAILED_STAGNANT
    stop_reason: str
