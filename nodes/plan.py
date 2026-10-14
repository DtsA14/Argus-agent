"""The orchestrator's plan: schema the model must fill in, and the rules the harness enforces on it.

The model submits a plan by calling the SubmitPlan tool. Pydantic checks the shape; validate_plan
adds the rules only the harness knows (output contract, max_workers, unique ids). Invalid plans are
returned to the model with the exact errors, a bounded number of times.
"""
import json

from pydantic import BaseModel, Field, ValidationError

from .contract import allowed_outputs, required_outputs

ID_PATTERN = r"^[A-Za-z][A-Za-z0-9_-]{0,19}$"


class PlanTask(BaseModel):
    """One unit of work for one worker."""
    id: str = Field(description="Short unique id, e.g. 'T1'. Letters, digits, '-' or '_', max 20 chars.")
    instruction: str = Field(description="What the worker must do, self-contained: the worker sees only this task.")
    output: str = Field(description="Name of the contract output this task produces.")
    feedback: str = Field(default="", description="On a revision: what was wrong last time and how to fix it.")


class SubmitPlan(BaseModel):
    """Submit the work plan. Call this exactly once."""
    tasks: list[PlanTask] = Field(description="Tasks to run in parallel, one per worker.")
    rationale: str = Field(default="", description="One or two sentences on how the work is split.")


def validate_plan(args, contract, max_workers):
    """Return (plan_dict, []) when valid, or (None, [error, ...]) with messages the model can act on."""
    try:
        plan = SubmitPlan.model_validate(args)
    except ValidationError as e:
        return None, [f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in e.errors()]

    import re
    errors = []
    tasks = plan.tasks
    if not tasks:
        errors.append("the plan has no tasks")
    if len(tasks) > max_workers:
        errors.append(f"the plan has {len(tasks)} tasks; at most {max_workers} are allowed")

    ids = [t.id for t in tasks]
    for t in tasks:
        if not re.match(ID_PATTERN, t.id):
            errors.append(f"task id {t.id!r} is invalid: use letters, digits, '-' or '_', start with a letter, max 20 chars")
        if len(t.instruction.strip()) < 10:
            errors.append(f"task {t.id!r}: instruction is too short to be self-contained")
        if len(t.instruction) > 4000:
            errors.append(f"task {t.id!r}: instruction is longer than 4000 characters")
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        errors.append(f"duplicate task ids: {dupes}")

    allowed = set(allowed_outputs(contract))
    outputs = [t.output for t in tasks]
    for t in tasks:
        if t.output not in allowed:
            errors.append(f"task {t.id!r}: output {t.output!r} is not in the contract; allowed: {sorted(allowed)}")
    for name in required_outputs(contract):
        n = outputs.count(name)
        if n == 0:
            errors.append(f"required output {name!r} is not produced by any task")
        elif n > 1:
            errors.append(f"output {name!r} is produced by {n} tasks; it must be produced exactly once")
    for name in sorted(allowed - set(required_outputs(contract))):
        if outputs.count(name) > 1:
            errors.append(f"output {name!r} is produced by {outputs.count(name)} tasks; at most once")

    if errors:
        return None, errors
    return plan.model_dump(), []


def system_prompt(contract, max_workers):
    outputs = "\n".join(
        f"- `{name}` ({'required' if o['required'] else 'optional'}): {o['description']}"
        for name, o in contract["outputs"].items()
    )
    return f"""You are the orchestrator of a small team of worker agents.

Your only job is to split the user's goal into tasks and submit them with the SubmitPlan tool.
You do not do the work yourself and you never see the data.

Rules (the harness rejects plans that break them):
- At most {max_workers} tasks. They run in parallel and cannot talk to each other.
- Each task produces exactly one contract output, named in its `output` field.
- Every required output is produced by exactly one task; optional outputs at most once.
- Each instruction must be self-contained: the worker sees only its own task, the data
  description and its tools, not the goal or the other tasks. State the exact output format.
- Task ids: start with a letter; letters, digits, '-' or '_'; max 20 characters; unique.

Contract outputs:
{outputs}

Data available to workers: {json.dumps(contract['data'], ensure_ascii=False)}

On a revision you receive the evaluator's failed checks. Keep what passed, fix what failed, and put
concrete guidance for the worker in that task's `feedback` field."""


def user_prompt(goal, previous_plan=None, failures=None):
    if previous_plan is None:
        return f"Goal:\n{goal}\n\nSubmit the plan."
    return (
        f"Goal:\n{goal}\n\n"
        f"Your previous plan:\n{json.dumps(previous_plan.get('tasks', []), ensure_ascii=False, indent=1)}\n\n"
        f"The evaluator rejected the result. Failed checks:\n"
        f"{json.dumps(failures or [], ensure_ascii=False, indent=1)}\n\n"
        "Submit a revised plan."
    )
