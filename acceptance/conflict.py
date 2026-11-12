"""The harness's check of an agent's `ReportConflict` (SPEC_REPORT_CONFLICT v1, v2 and v3).

The agent says: old protected tests contradict my change; the files are X. This does not take its word. Everything below is
the harness's own evidence, and what it proves is only the SHAPE: old tests that stood untouched fail with the agent's change
while the new required tests pass. Which side is wrong stays the human's call.

A report is `confirmed` only when all of these hold, else `unconfirmed` with the reasons (the attempt then fails as any
failed attempt does), or `blocked` when the sandbox is not there:
  1  every criterion outside the validations passes (scope, test detection, artifact, workspace unchanged, claims);
  2  every validation finished cleanly and says which of its tests are red (pytest and vitest keep per-test records; the
     list of red nodes is complete: failures plus errors equal what is listed);
  3  the red tests are in exactly the files the agent named (every red node in a named file, every named file red);
  4  each such file is an input file the agent did not touch, is protected (contract or repository), and is not a test the
     approved draft added or changed;
  5  every required test that is not red passes (so the new behaviour is there);
  6  the agent changed something besides SUMMARY.json;
  7  on the untouched input, those red tests pass (baseline: they were fine before);
  8  on the workspace, twice, they fail, each fails in a file that satisfies 4 (the deepest frame inside the repository, not
     an import or collection error), and the two runs agree (a flaky test does not confirm).
The red set comes from the validations' evidence in the verdict, never from SUMMARY.json or from the agent's text.
"""
from . import workspace as ws_mod
from .contract import SUMMARY, matches
from .validation import kind

MAX_FILES = 5
MAX_REASONS = 12


def file_of(node):
    return node.split("::", 1)[0]


def files_problem(files):
    """Why `files` cannot be a report's file list, or None: 1 to MAX_FILES distinct non-empty relative paths."""
    if not isinstance(files, list) or not 1 <= len(files) <= MAX_FILES:
        return f"files must be a list of 1 to {MAX_FILES} test files"
    for f in files:
        if (not isinstance(f, str) or not f or len(f) > 300 or "\x00" in f or f.startswith("/")
                or ".." in f.split("/")):
            return "each file must be a relative path of an existing test file"
    if len(set(files)) != len(files):
        return "files must not repeat"
    return None


def _untouched_old(path, before, after, protected, draft_files):
    """Why `path` cannot be a protected old test that stayed as the intake had it, or None (check 4)."""
    if path is None:
        return "no file of the repository in the failure"
    if path in draft_files:
        return f"{path} is a test the approved draft added or changed"
    if path not in before:
        return f"{path} is not a file of the input"
    if after.get(path) != before[path]:
        return f"{path} was changed by the agent"
    if not matches(path, protected):
        return f"{path} is not protected"
    return None


def verify(contract, verdict, files, *, ws, before, input_dir, scfg, repo_protected=(), draft_files=(), red, log=None):
    """The check, as a dict: {state: confirmed|unconfirmed|blocked, files, nodes, unconfirmed: [reasons], checks, reason}.
    red(nodes, workdir, scfg, timeout_s=, environment=, log=, runner=) -> (records, why, unavailable), the same shape as
    acceptance.validation.red_check_ex; tests inject their own. Never raises for anything the agent or the run can cause."""
    out = {"state": "unconfirmed", "files": files if isinstance(files, list) else [], "nodes": [], "unconfirmed": [],
           "checks": {}}

    def no(check, why):
        out["unconfirmed"].append(f"{check}: {why}")
        out["checks"][check] = why

    try:
        return _verify(contract, verdict, files, ws, before, input_dir, scfg, tuple(repo_protected), set(draft_files),
                       red, log, out, no)
    except Exception as e:                      # the harness's own bug must not turn into a confirmed conflict
        out["state"] = "unconfirmed"
        no("verification", f"could not be completed ({type(e).__name__})")
        return _final(out)


def _final(out):
    out["unconfirmed"] = out["unconfirmed"][:MAX_REASONS]
    out["reason"] = "; ".join(out["unconfirmed"]) if out["state"] != "confirmed" else ""
    return out


def _verify(contract, verdict, files, ws, before, input_dir, scfg, repo_protected, draft_files, red, log, out, no):
    bad = files_problem(files)
    if bad:
        no("files", bad)
        return _final(out)
    # 1  every criterion outside the validations
    for c in verdict["criteria"]:
        if c["layer"] != "C" and c["status"] != "pass":
            no("criteria", f"{c['id']} did not pass" + (f" ({c['reason'][:120]})" if c.get("reason") else ""))
    validations = [c for c in verdict["criteria"] if c["layer"] == "C"]
    specs = {f"validation:{v['id']}": v for v in contract["validation"]}
    if not validations:
        no("validations", "the contract has no validation")
    # 2  clean runs with a complete list of red nodes
    red_nodes = set()
    for c in validations:
        ev = c.get("evidence") or {}
        if ev.get("runner") not in ("pytest", "vitest"):
            no("validations", f"{c['id']} has no per-test records (only pytest and vitest runs are verified)")
            continue
        if (ev.get("timed_out") or ev.get("killed") or ev.get("output_limit_exceeded") or ev.get("truncated")
                or ev.get("consistent") is False or ev.get("tests_run") is None):
            no("validations", f"{c['id']} did not finish cleanly")
            continue
        listed = ev.get("failed_nodes") or []
        if (ev.get("failures") or 0) + (ev.get("errors") or 0) != len(listed):
            no("validations", f"{c['id']}: too many red tests to enumerate")
        red_nodes |= set(listed)
        for t, s in (ev.get("must_pass") or {}).items():          # 5  a required test that is not red passes
            if s != "ok" and t not in listed:
                no("must_pass", f"required test {t} did not pass")
    # 3  the red tests are in exactly the named files
    if not red_nodes:
        no("red", "nothing is red")
    named = set(files)
    stray = sorted(n for n in red_nodes if file_of(n) not in named)
    if stray:
        no("red", f"a red test is in a file the agent did not name: {stray[0]}")
    quiet = sorted(f for f in named if not any(file_of(n) == f for n in red_nodes))
    if quiet:
        no("red", f"a named file has no red test: {quiet[0]}")
    # 6  the agent changed something
    after = ws_mod.snapshot(ws)
    d = ws_mod.diff(before, after)
    if not [p for p in d["added"] + d["removed"] + d["modified"] if p != SUMMARY]:
        no("diff", "the agent changed no file")
    # 4  the files of the red tests
    protected = list(contract["scope"]["protected"]) + list(repo_protected)
    for f in sorted({file_of(n) for n in red_nodes}):
        why = _untouched_old(f, before, after, protected, draft_files)
        if why:
            no("old_tests", why)
    if out["unconfirmed"]:
        return _final(out)

    # 7 and 8  the harness's own runs
    spec = next((specs[c["id"]] for c in validations if c["id"] in specs), None)
    kw = {"timeout_s": spec["timeout_s"], "environment": spec.get("environment"), "log": log,
          "runner": "vitest" if kind(spec) == "vitest" else "pytest"}
    nodes = sorted(red_nodes)
    base, why, unavailable = red(nodes, input_dir, scfg, **kw)
    if unavailable:
        out["state"] = "blocked"
        out["unconfirmed"] = []
        out["reason"] = why
        return out
    if base is None:
        no("baseline", f"the run on the untouched input could not be read ({why})")
        return _final(out)
    for n in nodes:
        if (base.get(n) or {}).get("outcome") != "passed":
            no("baseline", f"{n} does not pass on the untouched input")
    if out["unconfirmed"]:
        return _final(out)
    runs = []
    for _ in range(2):
        got, why, unavailable = red(nodes, ws, scfg, **kw)
        if unavailable:
            out["state"] = "blocked"
            out["unconfirmed"] = []
            out["reason"] = why
            return out
        if got is None:
            no("red", f"the run on the workspace could not be read ({why})")
            return _final(out)
        runs.append(got)
    for n in nodes:
        a, b = (r.get(n) or {} for r in runs)
        if a.get("outcome") != "failed":
            no("red", f"{n} does not fail when the harness runs it")
            continue
        if (a.get("outcome"), a.get("type"), a.get("path")) != (b.get("outcome"), b.get("type"), b.get("path")):
            no("red", f"{n} is not stable between two runs")
            continue
        why = _untouched_old(a.get("path"), before, after, protected, draft_files)
        if why:
            no("red", f"{n}: {why}")
    if out["unconfirmed"]:
        return _final(out)
    out["state"] = "confirmed"
    out["nodes"] = [{"file": file_of(n), "node": n, "type": (runs[0][n] or {}).get("type"),
                     "path": (runs[0][n] or {}).get("path")} for n in nodes]
    out["checks"] = {k: "pass" for k in ("criteria", "validations", "red", "must_pass", "diff", "old_tests", "baseline")}
    return _final(out)
