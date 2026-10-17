"""Drafts and their approval (M6 W2a): a typed draft of a task (plan, scope, validations, new tests, what cannot be
checked automatically) is checked deterministically and, only if a human approves it with a reference patch, becomes
a task: a contract and a task repository that the agent runs on. No model is involved here; a drafter (W2b) only
writes the same draft file.

What the draft never sets: the input repository (an intake, by name), the issue, the cost cap and the attempt limit.
Those come from the human approving it.

Checks, all on the intake snapshot plus the draft's new tests, in the sandbox:
  - the contract built from the draft is valid; each new test is a new .py file in the protected scope, never
    writable, and has at least one required node (must_pass) of its own;
  - baseline red: every required node of a new test is collected and fails by assertion (FAIL). An error, a node not
    collected, any other failing or erroring test in that validation, or output that does not account for itself
    rejects the draft. Required nodes of existing tests pass, and every validation without new nodes passes;
  - reference green: the human's reference patch, applied to a clean copy, changes only writable files (never a test
    of the draft or a protected file), and then every validation passes.
`unverifiable` is kept as reviewer notes; it is never a criterion and never counts as a pass.

Approval publishes, in this order, the record (fixtures/intake/<task>.json), the contract
(fixtures/contracts/<task>.json) and the task repository (fixtures/repos/<task>, the intake snapshot plus the new tests).
The record binds the intake (commit, tree, snapshot), every added file's hash, the task snapshot and the contract's
sha256. Setup refuses a task whose files or contract differ from it (codetask/run.py).
"""
import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from . import contract as ct
from . import intake
from .validation import kind, run_validation
from .workspace import diff, digest, snapshot

VERSION = 1
KEYS = {"draft_version", "base", "plan", "contract", "new_tests", "unverifiable"}
PLAN_KEYS = {"files", "steps", "risks"}
CONTRACT_KEYS = {"scope", "validation", "tools", "budget_profile"}
MAX_TEST_BYTES = 50_000


class DraftError(Exception):
    pass


def _strings(v, limit=50, length=500):
    return isinstance(v, list) and len(v) <= limit and all(isinstance(x, str) and 0 < len(x) <= length for x in v)


def validate_draft(d):
    """Problems with the shape of a draft, or []."""
    if not isinstance(d, dict):
        return ["a draft must be an object"]
    errors = [f"unknown key {k!r}" for k in sorted(set(d) - KEYS)] + [f"missing key {k!r}" for k in sorted(KEYS - set(d))]
    if errors:
        return errors
    if d["draft_version"] != VERSION:
        errors.append(f"draft_version must be {VERSION}")
    if not isinstance(d["base"], str) or not intake.NAME.match(d["base"]):
        errors.append("base must be the name of an intake")
    p = d["plan"]
    if not isinstance(p, dict) or set(p) != PLAN_KEYS or not all(_strings(p[k]) for k in PLAN_KEYS):
        errors.append("plan must have files, steps and risks, each a list of non-empty strings")
    c = d["contract"]
    if not isinstance(c, dict) or not {"scope", "validation"} <= set(c) or set(c) - CONTRACT_KEYS:
        errors.append(f"contract must have scope and validation, and only {sorted(CONTRACT_KEYS)}")
    tests = d["new_tests"]
    if not isinstance(tests, list) or not tests:
        errors.append("new_tests must name at least one new test file")
    else:
        paths = []
        for i, t in enumerate(tests):
            if not (isinstance(t, dict) and set(t) == {"path", "content"} and isinstance(t["content"], str)):
                errors.append(f"new_tests[{i}] must be {{path, content}}")
                continue
            path = t["path"]
            name = path.rsplit("/", 1)[-1] if isinstance(path, str) else ""
            if not intake._plain(path) or not name.startswith("test_") or not name.endswith(".py"):
                errors.append(f"new_tests[{i}].path must be a plain relative path to a test_*.py file")
            if len(t["content"].encode("utf-8")) > MAX_TEST_BYTES:
                errors.append(f"new_tests[{i}] is larger than {MAX_TEST_BYTES} bytes")
            paths.append(path)
        if len(set(paths)) != len(paths):
            errors.append("new_tests has duplicate paths")
    if not _strings(d["unverifiable"], limit=20):
        errors.append("unverifiable must be a list of non-empty strings (may be empty)")
    return errors


def build_contract(draft, *, task, workspace, issue, max_usd, max_iterations):
    """The task's contract: the draft's scope, validations, tools and profile; everything else from the human."""
    c = {"contract": task, "version": 1, "inputs": {"workspace": workspace, "issue": issue},
         "scope": draft["contract"]["scope"], "artifacts": [{"path": ct.SUMMARY, "type": "json", "schema": "claims_v2"}],
         "validation": draft["contract"]["validation"], "judge": [],
         "limits": {"max_usd": max_usd, "max_iterations": max_iterations}}
    for k in ("tools", "budget_profile"):
        if k in draft["contract"]:
            c[k] = draft["contract"][k]
    return c


def _new_nodes(spec, new_paths):
    return [n for n in spec.get("must_pass", []) if n.split("::", 1)[0] in new_paths]


def static_problems(draft, contract, base_files):
    """Problems found without running anything."""
    problems = [f"contract: {e}" for e in ct.validate(contract)]
    if problems:
        return problems
    sc, new_paths = contract["scope"], {t["path"] for t in draft["new_tests"]}
    for p in sorted(new_paths):
        if p in base_files:
            problems.append(f"new test {p} already exists in the intake (a draft adds tests, it never changes them)")
        if not ct.matches(p, sc["protected"]) or ct.matches(p, sc["writable"]):
            problems.append(f"new test {p} must be protected and not writable (the agent must not be able to edit it)")
    owned = {n.split("::", 1)[0] for v in contract["validation"] for n in _new_nodes(v, new_paths)}
    problems += [f"new test {p} has no required node (must_pass) of its own" for p in sorted(new_paths - owned)]
    for v in contract["validation"]:
        if _new_nodes(v, new_paths) and kind(v) != "pytest":
            problems.append(f"validation {v['id']}: required nodes of new tests need a pytest validation")
    return problems


def materialize(base_dir, draft, dest):
    """A copy of the intake snapshot plus the draft's new tests. Returns {new path: sha256}."""
    shutil.copytree(base_dir, dest, ignore=shutil.ignore_patterns("__pycache__"))
    added = {}
    for t in draft["new_tests"]:
        target = Path(dest) / t["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        data = t["content"].encode("utf-8")
        target.write_bytes(data)
        os.chmod(target, 0o644)
        added[t["path"]] = hashlib.sha256(data).hexdigest()
    return added


def baseline_problems(contract, new_paths, ws, sandbox_cfg, validate=run_validation):
    """Baseline red for the new tests, green for everything else. Returns (problems, per-validation evidence)."""
    problems, seen = [], {}
    for spec in contract["validation"]:
        v = validate(spec, str(ws), sandbox_cfg)
        e = v.get("evidence") or {}
        seen[spec["id"]] = {"status": v["status"], "must_pass": e.get("must_pass"), "failures": e.get("failures"),
                            "errors": e.get("errors")}
        new = _new_nodes(spec, new_paths)
        if v["status"] == "blocked":
            problems.append(f"validation {spec['id']} could not run: {v['reason']}")
            continue
        if not new:
            if v["status"] != "pass":
                problems.append(f"validation {spec['id']} has no new test and must pass on the baseline: {v['reason']}")
            continue
        if kind(spec) == "pytest" and not e.get("consistent"):
            problems.append(f"validation {spec['id']}: pytest output does not account for itself")
        must = e.get("must_pass") or {}
        for n in spec.get("must_pass", []):
            got = must.get(n)
            if n in new and got != "FAIL":
                why = "was not collected" if got is None else f"is {got!r}, not a failure by assertion"
                problems.append(f"new test {n} {why} on the baseline")
            if n not in new and got != "ok":
                problems.append(f"existing test {n} must pass on the baseline, is {got!r}")
        if e.get("errors") or e.get("failures") != len(new):
            problems.append(f"validation {spec['id']}: {e.get('failures')} failures and {e.get('errors')} errors on the "
                            f"baseline; exactly the {len(new)} new required tests may fail, and nothing may error")
    return problems, seen


def reference_problems(contract, new_paths, ws, patch, sandbox_cfg, validate=run_validation):
    """Apply the reference patch to a clean copy and require every validation to pass. Returns (problems, seen)."""
    before = snapshot(ws)
    intake.git(ws, "apply", "--whitespace=nowarn", str(Path(patch).resolve()))
    changed = diff(before, snapshot(ws))
    sc, problems = contract["scope"], []
    for path in changed["added"] + changed["modified"] + changed["removed"]:
        if path in new_paths or ct.matches(path, sc["protected"]) or not ct.matches(path, sc["writable"]):
            problems.append(f"the reference patch changes {path}, which is not writable (tests and protected files "
                            "are never part of a solution)")
    if not any(changed.values()):
        problems.append("the reference patch changes nothing")
    if problems:
        return problems, {"changed": changed}
    seen = {"changed": changed}
    for spec in contract["validation"]:
        v = validate(spec, str(ws), sandbox_cfg)
        seen[spec["id"]] = v["status"]
        if v["status"] != "pass":
            problems.append(f"validation {spec['id']} does not pass with the reference patch: {v['reason']}")
    return problems, seen


def check(draft, *, task, issue, max_usd, max_iterations, reference_patch, sandbox_cfg, root=".",
          validate=run_validation):
    """The full report on a draft. ok only when every check passed."""
    root = Path(root)
    report = {"task": task, "draft_sha256": hashlib.sha256(ct.canonical(draft).encode()).hexdigest(),
              "unverifiable": draft.get("unverifiable"), "ok": False}
    errors = validate_draft(draft)
    if errors:
        return {**report, "problems": [f"draft: {e}" for e in errors]}
    base = intake.record_for(f"fixtures/repos/{draft['base']}", root)
    if base is None or base.get("kind", "intake") != "intake":
        return {**report, "problems": [f"no intake named {draft['base']!r}"]}
    base_dir = root / "fixtures" / "repos" / draft["base"]
    problems = intake.check(base, base_dir)
    if problems:
        return {**report, "problems": [f"intake {draft['base']}: {p}" for p in problems]}
    contract = build_contract(draft, task=task, workspace=f"fixtures/repos/{task}", issue=issue, max_usd=max_usd,
                              max_iterations=max_iterations)
    report["contract"] = contract
    problems = static_problems(draft, contract, snapshot(base_dir, skip_cache=True))
    if problems:
        return {**report, "problems": problems}
    new_paths = {t["path"] for t in draft["new_tests"]}
    with tempfile.TemporaryDirectory() as tmp:
        red = Path(tmp) / "baseline"
        report["added"] = materialize(base_dir, draft, red)
        problems, report["baseline"] = baseline_problems(contract, new_paths, red, sandbox_cfg, validate)
        if not problems:
            green = Path(tmp) / "reference"
            materialize(base_dir, draft, green)
            try:
                problems, report["reference"] = reference_problems(contract, new_paths, green, reference_patch,
                                                                   sandbox_cfg, validate)
            except intake.IntakeError as e:
                problems = [f"the reference patch does not apply to the baseline: {e}"]
    report["problems"] = problems
    report["ok"] = not problems
    return report


def approve(report, draft, *, root="."):
    """Publish an approved task from an ok report: the record, then the contract, then the task repository. Never
    overwrites. A stop part-way leaves a record without its task repository or contract, which setup refuses."""
    if not report.get("ok"):
        raise DraftError("only a report whose checks all passed can be approved")
    root, task = Path(root), report["task"]
    if not intake.NAME.match(task or ""):
        raise DraftError(f"task {task!r} must be a lower-case name")
    dest = root / "fixtures" / "repos" / task
    record_path = root / "fixtures" / "intake" / f"{task}.json"
    contract_path = root / "fixtures" / "contracts" / f"{task}.json"
    if dest.exists() or record_path.exists() or contract_path.exists():
        raise DraftError(f"task {task!r} already exists; approval never overwrites")
    base = intake.record_for(f"fixtures/repos/{draft['base']}", root)
    contract = report["contract"]
    _, contract_sha = ct.freeze(contract)
    (root / "fixtures" / "repos").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root / "fixtures" / "repos", prefix=".task-") as tmp:
        stage = Path(tmp) / task
        added = materialize(root / "fixtures" / "repos" / draft["base"], draft, stage)
        if added != report["added"]:
            raise DraftError("the new tests differ from the ones that were checked")
        snap = snapshot(stage)
        record = {"intake_version": intake.VERSION, "kind": "task", "name": task, "repo": base["repo"],
                  "commit": base["commit"], "tree": base["tree"], "exclude": base["exclude"],
                  "base": {k: base[k] for k in ("name", "commit", "tree", "snapshot_sha256")}, "added": added,
                  "files": len(snap), "snapshot_sha256": digest(snap), "executable": base["executable"],
                  "contract_sha256": contract_sha, "draft_sha256": report["draft_sha256"],
                  "plan": draft["plan"], "unverifiable": draft["unverifiable"],
                  "approved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
        for path, text in ((record_path, json.dumps(record, indent=2) + "\n"),
                           (contract_path, json.dumps(contract, indent=2, ensure_ascii=False) + "\n")):
            path.parent.mkdir(parents=True, exist_ok=True)
            part = path.with_name(f".{path.name}.part")
            part.write_text(text, encoding="utf-8")
            os.replace(part, path)
        os.replace(stage, dest)
    return record
