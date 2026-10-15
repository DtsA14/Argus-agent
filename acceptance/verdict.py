"""The acceptance verdict: every criterion of layers A-D with its evidence, and one outcome.

  pass     every criterion passed
  fail     at least one criterion failed and none is blocked
  blocked  at least one criterion could not be verified (e.g. no sandbox); never a pass, and retrying the agent
           does not help, so it wins over fail

Layer E (budget and time) is enforced by the run itself (LLMCaller, reservations, validation timeouts), not here.
"""
import hashlib

from . import claims as cl
from .contract import SUMMARY
from .validation import run_validation
from .workspace import diff, digest, scope_check, snapshot


def outcome(criteria):
    statuses = {c["status"] for c in criteria}
    if "blocked" in statuses:
        return "blocked"
    return "fail" if "fail" in statuses else "pass"


def evaluate(contract, workspace, before, sandbox_cfg, log=None, run=run_validation):
    after = snapshot(workspace)
    criteria = scope_check(contract, before, after)

    doc, problems = cl.read_summary(workspace)
    art = {"path": SUMMARY, "sha256": after.get(SUMMARY)}
    criteria.append({"id": f"artifact:{SUMMARY}", "layer": "B", "status": "fail" if problems else "pass",
                     "reason": "; ".join(problems), "evidence": art})

    validations = {}
    for spec in contract["validation"]:
        v = run(spec, workspace, sandbox_cfg, log)
        validations[v["id"]] = v
        criteria.append(v)

    if problems:
        criteria.append({"id": "claims", "layer": "D", "status": "fail",
                         "reason": f"no valid {SUMMARY}, so no completion claim can be checked", "evidence": {}})
    else:
        criteria += cl.check_claims(doc, validations, diff(before, after))

    # The verdict holds only for the workspace it was reached on: validation mounts it read-only, and this
    # confirms nothing changed while the criteria were being checked.
    final = snapshot(workspace)
    same = final == after
    criteria.append({"id": "workspace:unchanged_during_evaluation", "layer": "B",
                     "status": "pass" if same else "fail",
                     "reason": "" if same else f"workspace changed during evaluation: {diff(after, final)}",
                     "evidence": {}})
    return {"outcome": outcome(criteria), "criteria": criteria, "workspace_digest": digest(after),
            "summary_sha256": art["sha256"],
            "verdict_sha256": hashlib.sha256(repr(sorted((c["id"], c["status"]) for c in criteria))
                                             .encode("utf-8")).hexdigest()}
