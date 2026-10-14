from langgraph.types import Send

from harness.errors import PlanRejected

TASKS = [
    {"id": "T1", "desc": "Read and validate the CSV (columns, empty values)"},
    {"id": "T2", "desc": "Compute the top 3 products by revenue"},
    {"id": "T3", "desc": "Compute the monthly revenue trend"},
]

CRITERIA = [
    {"kind": "code", "desc": "laporan.md exists and lists 3 products"},
    {"kind": "code", "desc": "revenue in the report equals the script's recomputation"},
    {"kind": "code", "desc": "trend covers every month in the data"},
    {"kind": "rubric", "desc": "2 specific recommendations backed by numbers"},
]


def make_orchestrator(log, usd=0.0):
    def orchestrator(state):
        verdict = state.get("verdict") or {}
        fix_ids = sorted(
            {f["task"] for f in verdict.get("failures", []) if f["task"] in {"T1", "T2", "T3"}}
        )
        spec = state.get("spec")
        if spec is None:
            spec = {"goal": state["goal"], "tasks": TASKS, "criteria": CRITERIA, "revision": 0, "fix_ids": []}
            log.emit("spec_created", tasks=[t["id"] for t in TASKS], criteria=len(CRITERIA))
        else:
            spec = {**spec, "revision": spec["revision"] + 1, "fix_ids": fix_ids}
            log.emit("spec_revised", revision=spec["revision"], fix_ids=fix_ids)
        return {"spec": spec, "tokens_used": 3000, "usd_used": usd, "status": "RUNNING"}

    return orchestrator


def make_fan_out(max_workers, log):
    """Fan-out: one parallel worker per task; each gets only its own slice of context.

    The harness refuses plans wider than max_workers, because the iteration's token
    reservation was sized for at most that many workers.
    """

    def fan_out(state):
        tasks = state["spec"]["tasks"]
        if len(tasks) > max_workers:
            log.emit("plan_rejected", tasks=len(tasks), max_workers=max_workers)
            raise PlanRejected(f"orchestrator planned {len(tasks)} tasks, max_workers is {max_workers}")
        return _sends(state)

    return fan_out


def _sends(state):
    spec = state["spec"]
    return [
        Send(
            "worker",
            {
                "task": t,
                "iteration": state.get("iteration", 0),
                "fix_ids": spec.get("fix_ids", []),
                "scenario": state["scenario"],
                "run_id": state["run_id"],
            },
        )
        for t in spec["tasks"]
    ]
