"""Drafts and their approval (M6 W2a): a typed draft of a task (plan, scope, validations, new tests, what cannot be
checked automatically) is checked deterministically and, only if a human approves it with a reference patch, becomes
a task: a contract and a task repository that the agent runs on. No model is involved here; a drafter (W2b) only
writes the same draft file.

What the draft never sets: the input repository (an intake, by name), the issue, the cost cap and the attempt limit.
Those come from the human approving it.

Checks, all on the intake snapshot plus the draft's new tests, in the sandbox:
  - the contract built from the draft is valid; each new test is a new test_*.py file (a *.test.js|jsx|ts|tsx file
    when the draft's validations run vitest, SPEC_PWA_VIEWER; one runner per draft, no changed_tests for vitest) in
    the protected scope, never writable, and has at least one required node (must_pass) of its own;
  - baseline red: every required node of a new test is collected and fails by assertion (FAIL). An error, a node not
    collected, any other failing or erroring test in that validation, or output that does not account for itself
    rejects the draft. Required nodes of existing tests pass, and every validation without new nodes passes;
  - reference green: the human's reference patch (a git diff against the intake plus the draft's tests), applied to a
    clean copy, changes only writable files (never a test
    of the draft or a protected file), and then every validation passes.
    W2b (docs/reviews/SPEC_W2B_DRAFTER.md, K1): the reference patch is optional. Without one (reference_patch=None)
    this check is skipped and the report and the record say `feasibility: "unproven"`: the criteria are then not known
    to be satisfiable, and an agent that cannot meet them fails its run. Everything else is checked the same.
`unverifiable` is kept as reviewer notes; it is never a criterion and never counts as a pass.

W2a-ext (docs/reviews/SPEC_W2A_EXT_CHANGED_TESTS.md): a draft may also change existing test files (`changed_tests`,
acceptance/changed.py). The baseline is then the intake plus the new tests plus the changed files; the required nodes
of a changed file are red like those of a new test; no old node is lost and no test function changes unless the draft
names it (removed / modified, with a reason); and no node of a changed file may end skipped or xfail unless the intake
version marks it so (the contract's no_skip, for the baseline, the reference and the agent alike).

Approval publishes, in this order, the record (fixtures/intake/<task>.json), the contract
(fixtures/contracts/<task>.json) and the task repository (fixtures/repos/<task>, the intake snapshot plus the new tests).
The record binds the intake (commit, tree, snapshot), every added file's hash, the task snapshot and the contract's
sha256. Setup refuses a task whose files or contract differ from it (codetask/run.py).
"""
import copy
import hashlib
import json
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from . import changed as ch
from . import contract as ct
from . import intake
from .validation import MAX_NODES, VITEST_FILE, collect_nodes, kind, red_check, run_validation
from .workspace import diff, digest, snapshot

VERSION = 1
KEYS = {"draft_version", "base", "plan", "contract", "new_tests", "unverifiable"}
OPTIONAL_KEYS = {"changed_tests"}                 # W2a-ext; absent is the same as []
PLAN_KEYS = {"files", "steps", "risks"}
CONTRACT_KEYS = {"scope", "validation", "tools", "budget_profile"}
MAX_TEST_BYTES = 50_000


class DraftError(Exception):
    pass


def _strings(v, limit=50, length=500):
    return isinstance(v, list) and len(v) <= limit and all(isinstance(x, str) and 0 < len(x) <= length for x in v)


def _strings_problem(name, v, limit=50, length=500):
    """Why `v` is not a list of at most `limit` non-empty strings of at most `length` characters, naming the item, or
    None. (argus-ledger stage 4: "each a list of non-empty strings" hid a 548-character step; three submits went on it.)"""
    if not isinstance(v, list):
        return f"{name} must be a list of strings, not {type(v).__name__}"
    if len(v) > limit:
        return f"{name} has {len(v)} items, at most {limit}"
    for i, x in enumerate(v):
        if not isinstance(x, str) or not x:
            return f"{name}[{i}] must be a non-empty string"
        if len(x) > length:
            return f"{name}[{i}] has {len(x)} characters, at most {length}: shorten it or split it into two items"
    return None


def validate_draft(d):
    """Problems with the shape of a draft, or []."""
    if not isinstance(d, dict):
        return ["a draft must be an object"]
    errors = [f"unknown key {k!r}" for k in sorted(set(d) - KEYS - OPTIONAL_KEYS)]
    errors += [f"missing key {k!r}" for k in sorted(KEYS - set(d))]
    if errors:
        return errors
    if d["draft_version"] != VERSION:
        errors.append(f"draft_version must be {VERSION}")
    if not isinstance(d["base"], str) or not intake.NAME.match(d["base"]):
        errors.append("base must be the name of an intake")
    p = d["plan"]
    if not isinstance(p, dict) or set(p) != PLAN_KEYS:
        errors.append("plan must have files, steps and risks, each a list of non-empty strings")
    else:
        errors += [why for k in sorted(PLAN_KEYS) if (why := _strings_problem(f"plan.{k}", p[k]))]
    c = d["contract"]
    if not isinstance(c, dict) or not {"scope", "validation"} <= set(c) or set(c) - CONTRACT_KEYS:
        errors.append(f"contract must have scope and validation, and only {sorted(CONTRACT_KEYS)}")
    elif isinstance(c["validation"], list) and any(isinstance(v, dict) and "no_skip" in v for v in c["validation"]):
        errors.append("no_skip is set by the harness, never by a draft")
    elif isinstance(c.get("tools"), list) and set(c["tools"]) & ct.HUMAN_TOOLS:
        errors.append(f"tools: {sorted(set(c['tools']) & ct.HUMAN_TOOLS)} are granted by the human at approve "
                      "(argus approve --web), never by a draft")
    runners = draft_runners(c)
    if len(runners) > 1:
        errors.append(f"a draft's validations must all use one runner (vitest, or Python's), not {sorted(runners)}")
    vitest = runners == {"vitest"}
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
            if len(runners) > 1:
                pass                                  # which test files fit is unknown until there is one runner
            elif vitest and not (isinstance(path, str) and intake._plain(path) and VITEST_FILE.match(path)):
                errors.append(f"new_tests[{i}].path must be a plain relative path to a vitest test file "
                              "(*.test.js, .jsx, .ts or .tsx)")
            elif not vitest and (not intake._plain(path) or not name.startswith("test_") or not name.endswith(".py")):
                errors.append(f"new_tests[{i}].path must be a plain relative path to a test_*.py file")
            if len(t["content"].encode("utf-8")) > MAX_TEST_BYTES:
                errors.append(f"new_tests[{i}] is larger than {MAX_TEST_BYTES} bytes")
            paths.append(path)
        if len(set(paths)) != len(paths):
            errors.append("new_tests has duplicate paths")
    why = _strings_problem("unverifiable", d["unverifiable"], limit=20)
    if why:
        errors.append(why + " (unverifiable may be empty)")
    if "changed_tests" in d and vitest and d["changed_tests"]:
        errors.append("changed_tests are not supported for vitest (SPEC_PWA_VIEWER v0: the old-test comparison is "
                      "Python's AST; a vitest draft only adds test files)")
    elif "changed_tests" in d:
        new_paths = [t.get("path") for t in tests if isinstance(t, dict)] if isinstance(tests, list) else []
        errors += ch.shape_problems(d["changed_tests"], new_paths, intake._plain, MAX_TEST_BYTES)
    return errors


def draft_runners(c):
    """{"vitest"} or {"pytest"} (unittest included: both Python) of a draft contract's validations; empty when they
    cannot be read yet (their shape is checked elsewhere)."""
    vals = c.get("validation") if isinstance(c, dict) else None
    return {"vitest" if kind(v) == "vitest" else "pytest" for v in vals or [] if isinstance(v, dict)} \
        if isinstance(vals, list) else set()


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def old_tests(base_dir, draft):
    """{path: the intake version's text, or None} of the draft's changed test files."""
    out = {}
    for t in draft.get("changed_tests") or []:
        p = Path(base_dir) / t["path"]
        try:
            out[t["path"]] = p.read_bytes().decode("utf-8") if p.is_file() and not p.is_symlink() else None
        except (OSError, UnicodeDecodeError):
            out[t["path"]] = None
    return out


def build_contract(draft, *, task, workspace, issue, max_usd, max_iterations, old=None, web=False):
    """The task's contract: the draft's scope, validations, tools and profile; everything else from the human.
    old: {path: intake text} of the changed test files (old_tests), from which their no_skip rules are made.
    web: the human granted ReadDocs (SPEC_WEB_TOOLS 3): read_docs is added to the draft's tools."""
    c = {"contract": task, "version": 1, "inputs": {"workspace": workspace, "issue": issue},
         "scope": copy.deepcopy(draft["contract"]["scope"]),
         "artifacts": [{"path": ct.SUMMARY, "type": "json", "schema": "claims_v2"}],
         "validation": copy.deepcopy(draft["contract"]["validation"]), "judge": [],
         "limits": {"max_usd": max_usd, "max_iterations": max_iterations}}
    for k in ("tools", "budget_profile"):
        if k in draft["contract"]:
            c[k] = copy.deepcopy(draft["contract"][k])
    if web:
        c["tools"] = [t for t in c.get("tools") or [] if t != "read_docs"] + ["read_docs"]
    if draft.get("changed_tests"):
        ch.add_no_skip(c["validation"], {t["path"]: (old or {}).get(t["path"]) for t in draft["changed_tests"]})
    return c


def _new_nodes(spec, new_paths):
    return [n for n in spec.get("must_pass", []) if n.split("::", 1)[0] in new_paths]


def red_paths(draft):
    """The files whose required nodes must fail on the baseline: the new tests and the changed ones."""
    return {t["path"] for t in draft["new_tests"]} | {t["path"] for t in draft.get("changed_tests") or []}


def repo_protected_problems(draft, contract, base_files, protected):
    """SPEC_PROTECTED_FILES P3/K3: no file of the intake that the repository protects (its .argus/protected, in the
    intake record) may be writable, and no changed test may be one of them. A file that is not writable is safe even
    when the contract's protected globs do not name it; new test files may match the list (they are new)."""
    globs = (protected or {}).get("globs") or []
    if not globs:
        return []
    sc = contract["scope"]
    # the intake's listed files, and every list entry that names one path (a file the commit lacks, or one the job's
    # exclude left out, such as .argus/protected itself): none may be writable
    listed = sorted({f for f in base_files if ct.matches(f, globs)}
                    | {g for g in globs if not any(c in g for c in "*?")})
    problems = [f"{f} is protected by the repository ({intake.PROTECTED_FILE}), but writable glob {g!r} matches it"
                for f in listed for g in sc["writable"] if ct.matches(f, [g])]
    problems += [f"changed test {t['path']} is protected by the repository ({intake.PROTECTED_FILE}): it is changed "
                 "only by a commit of the human, never through a draft"
                 for t in draft.get("changed_tests") or [] if ct.matches(t["path"], globs)]
    return problems


#: A file vitest's default `include` takes for a test (`**/*.{test,spec}.?(c|m)[jt]s?(x)`); one that VITEST_FILE does not
#: match cannot be named in a validation (SPEC_VITEST_FULL_REGRESSION F1b).
VITEST_LIKE = re.compile(r"\.(?:test|spec)\.(?:c|m)?[jt]sx?$")


def full_regression_problems(draft, contract, base_files):
    """SPEC_VITEST_FULL_REGRESSION F1: a vitest draft names every existing test file of the intake (base_files: the job
    commit's snapshot; the draft's new tests are not existing ones) in a vitest validation, so the whole old suite must
    pass wherever the validations run. F1b: a file vitest would take for a test but VITEST_FILE does not match is
    refused, so none goes uncounted. node_modules is never a test of the repository (vitest excludes it too)."""
    if draft_runners(draft["contract"]) != {"vitest"}:
        return []
    new = {t["path"] for t in draft["new_tests"]}
    named = {f for v in contract["validation"] if kind(v) == "vitest" for f in v["args"][1:]}
    problems = []
    for f in sorted(base_files):
        if f in new or "node_modules" in f.split("/"):
            continue
        if VITEST_FILE.match(f) and intake._plain(f):
            if f not in named:
                problems.append(f"existing test file {f} is in no validation (a vitest draft runs every existing "
                                "test file)")
        elif VITEST_LIKE.search(f.rsplit("/", 1)[-1]):
            problems.append(f"test file {f} cannot be run by the harness (only *.test.js|jsx|ts|tsx with plain "
                            "names): rename it in the repository")
    return problems


def static_problems(draft, contract, base_files, old=None):
    """Problems found without running anything. old: old_tests() of the draft (needed for changed_tests)."""
    problems = [f"contract: {e}" for e in ct.validate(contract)]
    if problems:
        return problems
    problems += ch.static_problems(draft, contract, base_files, old or {}, _sha)
    sc, new_paths = contract["scope"], {t["path"] for t in draft["new_tests"]}
    for p in sorted(new_paths):
        if p in base_files:
            problems.append(f"new test {p} already exists in the intake (a draft adds tests, it never changes them)")
        if not ct.matches(p, sc["protected"]) or ct.matches(p, sc["writable"]):
            problems.append(f"new test {p} must be protected and not writable (the agent must not be able to edit it)")
    owned = {n.split("::", 1)[0] for v in contract["validation"] for n in _new_nodes(v, new_paths)}
    problems += [f"new test {p} has no required node (must_pass) of its own" for p in sorted(new_paths - owned)]
    for v in contract["validation"]:
        if _new_nodes(v, red_paths(draft)) and kind(v) not in ("pytest", "vitest"):
            problems.append(f"validation {v['id']}: required nodes of new or changed tests need a pytest or vitest "
                            "validation")
    return problems + full_regression_problems(draft, contract, base_files)


def changed_record(base_files, draft):
    """{path: {before, after, removed, modified}} of the draft's changed tests: the record's `changed`."""
    return {t["path"]: {"before": base_files.get(t["path"]), "after": _sha(t["content"]),
                        "removed": t.get("removed", []), "modified": t.get("modified", [])}
            for t in draft.get("changed_tests") or []}


def materialize(base_dir, draft, dest):
    """A copy of the intake snapshot plus the draft's new tests and changed tests. Returns {new path: sha256}."""
    shutil.copytree(base_dir, dest, ignore=shutil.ignore_patterns("__pycache__"))
    added = {}
    for t in draft.get("changed_tests") or []:
        target = Path(dest) / t["path"]
        target.unlink()
        target.write_bytes(t["content"].encode("utf-8"))
        os.chmod(target, 0o644)
    for t in draft["new_tests"]:
        target = Path(dest) / t["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        data = t["content"].encode("utf-8")
        target.write_bytes(data)
        os.chmod(target, 0o644)
        added[t["path"]] = hashlib.sha256(data).hexdigest()
    return added


def collection_problems(draft, contract, base_dir, ws, sandbox_cfg, collect=collect_nodes):
    """K1: each changed file collected in the sandbox from the intake (base_dir) and from the baseline (ws), with the
    environment and timeout of a validation that runs it whole. Returns (problems, per-file evidence)."""
    problems, seen = [], {}
    for t in draft.get("changed_tests") or []:
        p = t["path"]
        spec = next(v for v in contract["validation"] if ch.runs_whole(v, p))      # static_problems: one exists
        kw = {"timeout_s": spec["timeout_s"], "environment": spec.get("environment")}
        got = {}
        for side, where in (("intake", base_dir), ("new", ws)):
            got[side], why = collect(p, str(where), sandbox_cfg, **kw)
            if got[side] is None:
                problems.append(f"changed test {p}: the {side} version could not be collected: {why}")
                break
        else:
            problems += ch.lost_problems(p, got["intake"], got["new"], [r["node"] for r in t.get("removed", [])])
            seen[p] = {"intake": len(got["intake"]), "new": len(got["new"]),
                       "gone": sorted(got["intake"] - got["new"])[:MAX_NODES]}
    return problems, seen


# A failure that is not an assertion of the test itself fails whatever the fix is (pilot W2b-3: KeyError in a drafted test)
NOT_ASSERTION_HINT_VITEST = ("check with expect() first: expect(screen.queryByText(\"x\")).not.toBeNull() instead of "
                             "getByText, expect(report).toHaveProperty(\"key\") before report.key, and build in the "
                             "test every piece of data it uses")
NOT_ASSERTION_HINT = ("check with an assert first: `assert \"key\" in report` before `report[\"key\"]`, `assert hasattr(obj, "
                      "\"name\")` before calling it, and build in the test (or its fixture) every piece of data it uses")


def red_by_assertion(spec, nodes, ws, sandbox_cfg, contract, red_files, red=red_check):
    """Problems unless every node failed by an assertion of a test file (docs/reviews/SPEC_W2A_RED_BY_ASSERTION.md): an
    AssertionError or pytest.fail.Exception whose last frame in the repository is a new or changed test file, or a
    protected, non-writable helper in the directory of one. Returns (problems, records)."""
    got, why = red(nodes, str(ws), sandbox_cfg, timeout_s=spec["timeout_s"], environment=spec.get("environment"),
                   runner="vitest" if kind(spec) == "vitest" else "pytest")
    if got is None:
        return [f"validation {spec['id']}: how its required tests fail could not be read: {why}"], None
    sc, dirs = contract["scope"], {p.rsplit("/", 1)[0] + "/" for p in red_files if "/" in p}
    problems = []
    for n in nodes:
        rec = got.get(n)
        path = (rec or {}).get("path") or ""
        test_file = path in red_files or (any(path.startswith(d) for d in dirs) and ct.matches(path, sc["protected"])
                                          and not ct.matches(path, sc["writable"]))
        if isinstance(rec, dict) and rec.get("outcome") == "error":     # SPEC_RED_TESTS_PER_NODE 2.2
            problems.append(f"required test {n} errors in its setup or teardown (a fixture), before or after the test "
                            "itself runs: it must fail by an assertion in the test; build the data the test needs in "
                            "the test or a fixture that cannot fail on the old code")
        elif not isinstance(rec, dict) or rec.get("outcome") != "failed":
            problems.append(f"required test {n}: no record of how it fails (it must fail by an assertion)")
        elif not rec.get("assertion"):
            hint = NOT_ASSERTION_HINT_VITEST if kind(spec) == "vitest" else NOT_ASSERTION_HINT
            problems.append(f"required test {n} fails with {rec.get('type')}, not by an assertion: it would fail "
                            f"whatever the fix is; {hint}")
        elif not test_file:
            problems.append(f"required test {n} fails by {rec.get('type')} raised in {path or 'no file of the repository'}"
                            ", not in a test file: the test itself checks nothing yet; assert on the result in the test")
    return problems, got


def baseline_problems(contract, new_paths, ws, sandbox_cfg, validate=run_validation, red=red_check):
    """Baseline red for the new tests (and the required nodes of changed tests: new_paths is red_paths()), green for
    everything else; red by an assertion of the test itself (red_by_assertion). Returns (problems, per-validation
    evidence)."""
    problems, seen = [], {}
    for spec in contract["validation"]:
        mark = len(problems)
        v = validate(spec, str(ws), sandbox_cfg)
        e = v.get("evidence") or {}
        # output_tail (W2b): the test output, for the drafter's feedback and the human's review; data, never a criterion
        seen[spec["id"]] = {"status": v["status"], "must_pass": e.get("must_pass"), "failures": e.get("failures"),
                            "errors": e.get("errors"), "output_tail": (e.get("output_tail") or "")[-2000:],
                            "failed_nodes": e.get("failed_nodes")}
        new = _new_nodes(spec, new_paths)
        if v["status"] == "blocked":
            problems.append(f"validation {spec['id']} could not run: {v['reason']}")
            continue
        if not new:
            if v["status"] != "pass":
                problems.append(f"validation {spec['id']} has no new test and must pass on the baseline: {v['reason']}")
            continue
        if e.get("skip_violations"):          # W2a-ext: judge_result names them; a red validation is read here
            problems.append(f"validation {spec['id']}: skipped or xfail in a changed test file, and not marked so "
                            f"before the change: {', '.join(e['skip_violations'])}")
        if kind(spec) in ("pytest", "vitest") and not e.get("consistent"):
            problems.append(f"validation {spec['id']}: {kind(spec)} output does not account for itself")
        must = e.get("must_pass") or {}
        for n in spec.get("must_pass", []):
            got = must.get(n)
            if n in new and got != "FAIL":
                why = "was not collected" if got is None else f"is {got!r}, not a failure by assertion"
                problems.append(f"new test {n} {why} on the baseline")
            if n not in new and got != "ok":
                problems.append(f"existing test {n} must pass on the baseline, is {got!r}")
        if e.get("errors") or e.get("failures") != len(new):
            extra = [n for n in e.get("failed_nodes") or [] if n not in new]      # W2b: name them, so a fix can be exact
            problems.append(f"validation {spec['id']}: {e.get('failures')} failures and {e.get('errors')} errors on the "
                            f"baseline; exactly the {len(new)} new required tests may fail, and nothing may error"
                            + (f" (failing or erroring but not required: {', '.join(extra)})" if extra else ""))
        if len(problems) == mark:     # the red nodes are known to FAIL; now why (only when the rest of it holds)
            more, seen[spec["id"]]["red_check"] = red_by_assertion(spec, new, ws, sandbox_cfg, contract, new_paths, red)
            problems += more
    return problems, seen


def reference_problems(contract, new_paths, ws, patch, sandbox_cfg, validate=run_validation):
    """Apply the reference patch to a clean copy and require every validation to pass. Returns (problems, seen)."""
    if not Path(patch).read_text(encoding="utf-8").strip():
        return ["the reference patch changes nothing"], {}
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
          profiles, validate=run_validation, collect=collect_nodes, red=red_check, web=False):
    """The full report on a draft. ok only when every check passed. reference_patch=None: no reference check (W2b),
    and the report says the criteria are not proven satisfiable. profiles (required, no default, so a new caller
    cannot skip the check by forgetting it): the configured budget profile names, for the checks setup runs
    (ct.setup_problems); only an explicit profiles=None leaves the profile to setup. The sandbox environments are
    checked as setup checks them: against sandbox_cfg's environments, none when it has no such key."""
    root = Path(root)
    report = {"task": task, "draft_sha256": hashlib.sha256(ct.canonical(draft).encode()).hexdigest(),
              "unverifiable": draft.get("unverifiable"), "ok": False,
              "feasibility": "unproven" if reference_patch is None else "proven"}
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
    old = old_tests(base_dir, draft)
    contract = build_contract(draft, task=task, workspace=f"fixtures/repos/{task}", issue=issue, max_usd=max_usd,
                              max_iterations=max_iterations, old=old, web=web)
    report["contract"] = contract
    base_files = snapshot(base_dir, skip_cache=True)
    problems = static_problems(draft, contract, base_files, old)
    if not problems:
        problems = repo_protected_problems(draft, contract, base_files, base.get("protected"))
    if not problems:              # what setup checks before the agent, on the task baseline's files (W2b-3 run 2)
        task_files = set(base_files) | {t["path"] for t in draft["new_tests"]}
        problems = [f"contract: {p}" for p in ct.setup_problems(
            contract, task_files, profiles=profiles,
            environments_configured=(sandbox_cfg.get("environments") or {}) if sandbox_cfg else None)]
    if not problems:
        report["contract_sha256"] = ct.freeze(contract)[1]        # what approve() must still be publishing
    if problems:
        return {**report, "problems": problems}
    new_paths = red_paths(draft)
    if draft.get("changed_tests"):
        report["changed"] = changed_record(base_files, draft)
        report["warnings"] = [w for t in draft["changed_tests"]
                              for w in ch.warnings(t["path"], old[t["path"]], t["content"], t.get("removed", []))]
    with tempfile.TemporaryDirectory() as tmp:
        red_dir = Path(tmp) / "baseline"
        report["added"] = materialize(base_dir, draft, red_dir)
        problems = []
        if draft.get("changed_tests"):
            problems, report["collection"] = collection_problems(draft, contract, base_dir, red_dir, sandbox_cfg, collect)
        if not problems:
            problems, report["baseline"] = baseline_problems(contract, new_paths, red_dir, sandbox_cfg, validate, red)
        if not problems and reference_patch is None:
            report["reference"] = None
        elif not problems:
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
    # Publish exactly what was checked: the same draft, the same contract, and a contract that is the draft plus the
    # human's fields (so neither can be swapped between check() and approve(), by any caller). Before anything is
    # written.
    if hashlib.sha256(ct.canonical(draft).encode()).hexdigest() != report.get("draft_sha256"):
        raise DraftError("the draft differs from the one that was checked")
    contract = report.get("contract")
    try:
        _, contract_sha = ct.freeze(contract)
    except ct.ContractError as e:
        raise DraftError(f"the report's contract is not valid: {e}") from e
    if contract_sha != report.get("contract_sha256"):
        raise DraftError("the contract differs from the one that was checked")
    base = intake.record_for(f"fixtures/repos/{draft['base']}", root)
    base_dir = root / "fixtures" / "repos" / draft["base"]
    stale = ["no intake"] if base is None else intake.check(base, base_dir)
    if stale:                      # the intake changed after the check: the tests ran on something else
        raise DraftError(f"intake {draft['base']} changed since the check: {'; '.join(stale)}")
    rebuilt = build_contract(draft, task=task, workspace=f"fixtures/repos/{task}", issue=contract["inputs"]["issue"],
                             max_usd=contract["limits"]["max_usd"], max_iterations=contract["limits"]["max_iterations"],
                             old=old_tests(base_dir, draft), web="read_docs" in (contract.get("tools") or []))
    if ct.canonical(rebuilt) != ct.canonical(contract):
        raise DraftError("the contract is not the draft plus the human's fields")
    changed = changed_record(snapshot(base_dir, skip_cache=True), draft)
    if changed != (report.get("changed") or {}):
        raise DraftError("the changed tests differ from the ones that were checked")
    (root / "fixtures" / "repos").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root / "fixtures" / "repos", prefix=".task-") as tmp:
        stage = Path(tmp) / task
        added = materialize(base_dir, draft, stage)
        if added != report["added"]:
            raise DraftError("the new tests differ from the ones that were checked")
        snap = snapshot(stage)
        record = {"intake_version": intake.VERSION, "kind": "task", "name": task, "repo": base["repo"],
                  "commit": base["commit"], "tree": base["tree"], "exclude": base["exclude"],
                  "base": {k: base[k] for k in ("name", "commit", "tree", "snapshot_sha256")}, "added": added,
                  "files": len(snap), "snapshot_sha256": digest(snap), "executable": base["executable"],
                  "protected": base.get("protected"), "contract_sha256": contract_sha, "draft_sha256": report["draft_sha256"],
                  "plan": draft["plan"], "unverifiable": draft["unverifiable"],
                  # W2b: "proven" only when a reference patch passed every validation in this report
                  "feasibility": "proven" if report.get("reference") else "unproven",
                  "approved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
        if changed:                    # W2a-ext: before/after hashes, and what the human approved removing or changing
            record["changed"] = changed
        for path, text in ((record_path, json.dumps(record, indent=2) + "\n"),
                           (contract_path, json.dumps(contract, indent=2, ensure_ascii=False) + "\n")):
            path.parent.mkdir(parents=True, exist_ok=True)
            part = path.with_name(f".{path.name}.part")
            part.write_text(text, encoding="utf-8")
            os.replace(part, path)
        os.replace(stage, dest)
    return record
