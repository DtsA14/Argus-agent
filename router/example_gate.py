"""SPEC_EXAMPLE_GATE PR 2 (sections 4(2), 4(3), 8 item 2): the examples of an issue as a gate on a code job, in three places that
all read the same block of the issue text:

  intake  the `same` and `whatif` examples run on the base tree before any drafter money; a wrong one BLOCKS the job
  audit   after the agent, every example runs on the base tree with the review package's patch applied; the result is kept
          per agent stage, bound to the patch's sha256 and to the examples, with a pending marker written first (fail closed:
          a run that did not finish leaves "pending", never "no result")
  apply   `argus apply` / `argus applied` decide from the issue text alone: a block with no finished audit for the patch
          that is applied, or with a failed example, is refused unless the human names exactly the failed ids

The block is a fenced code block of the issue text, ```argus-examples, whose body is a JSON list of examples (codetask/examples.py
defines them). An issue without the block has no gate: jobs from before this are applied as they were. Nothing here calls a model;
the example code runs through a `runner` (the sandbox in production). No new kind of job log entry is written: the results are
files in the job directory, and what apply decides is recorded as a field of the log entries that already exist.
"""
import hashlib
import json
import os
import re
from pathlib import Path

from acceptance import contract as ct
from codetask import examples as ex
from tools.sandbox import SandboxUnavailable

BOX_ROOT = "/workspace"                      # where the sandbox mounts the tree
INTAKE_FILE = "examples_intake.json"
FENCE = re.compile(r"^[ \t]*(`{3,}|~{3,})[ \t]*argus-examples[ \t]*\n(.*?)^[ \t]*\1[`~]*[ \t]*$", re.M | re.S | re.I)
LOOSE = re.compile(r"^[ \t]*(?:`{3,}|~{3,})[^\n]*argus-examples", re.M | re.I)      # any fence that mentions the word
STATUSES = (ex.PASS, ex.FAIL, ex.ERROR, ex.INVALID, ex.UNCHECKED)
RUNNER_NOTE = "environment without an example runner"
HOLDERS_MAX = 3


def sandbox_runner(tree, scfg):
    """(runner, root) of the sandbox for `tree`: the tree read-only at /workspace, no network; docker itself failing (exit 125 to
    127, a container that could not be cleaned up) is SandboxUnavailable, never an example's result."""
    from tools import sandbox

    def run(argv):
        r = sandbox.run_command(argv, workdir=tree, cfg=scfg)
        if r.get("exit_code") in (125, 126, 127) or r.get("cleanup_failed"):
            raise sandbox.SandboxUnavailable(f"the container did not run (exit {r.get('exit_code')})")
        return r
    return run, BOX_ROOT


def audit_file(job_dir, sid):
    return Path(job_dir) / f"examples_audit_{sid}.json"


# ---- the block --------------------------------------------------------------------------------------------------------

def extract(issue):
    """(present, examples, problems) of an issue text: present is whether it carries an argus-examples block at all (a job
    from before the gate has none); the examples are the parsed ones, the problems everything wrong with the block. Never
    raises on what a person or a model wrote."""
    if not isinstance(issue, str):
        return False, [], []
    issue = issue.replace("\r\n", "\n").replace("\r", "\n")
    found = FENCE.findall(issue)
    mentioned = len(LOOSE.findall(issue))
    if not found and not mentioned:
        return False, [], []
    if mentioned != len(found):                 # a fence that names the block but is not written exactly: never read as "no block"
        return True, [], ["a fence mentions argus-examples but is not a well-formed block (the fence line is exactly "
                          "```argus-examples, and it is closed)"]
    if len(found) > 1:
        return True, [], [f"the issue has {len(found)} argus-examples blocks; it takes one"]
    try:
        raw = json.loads(found[0][1])
    except (ValueError, RecursionError):
        return True, [], ["the argus-examples block is not JSON"]
    examples, problems = ex.parse(raw)
    return True, ([] if problems else examples), problems


def block_text(examples):
    """The block as the harness writes it into an issue: one example per line, so a human reads them one by one."""
    return "```argus-examples\n[\n" + ",\n".join(json.dumps(e, ensure_ascii=False) for e in examples) + "\n]\n```"


def with_block(issue, examples):
    """The issue as stored: with the block put before its last line (the Environment line), after any clash list; without
    examples, the issue as it is."""
    if not examples:
        return issue
    lines = issue.split("\n")
    if len(lines) < 2:
        return issue
    body = lines[:-1]
    while body and not body[-1].strip():
        body.pop()
    return "\n".join(body + [""] + block_text(examples).split("\n") + ["", lines[-1]])


def without_block(issue):
    """The issue without a block the harness wrote into it (and the blank line before it): a writer that gives back its stored
    issue does not get the block twice, and one that wrote its own gets it taken out."""
    text = issue.replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"\n*" + FENCE.pattern + r"\n*", "\n\n", text, flags=FENCE.flags)


def mentions(issue):
    """True when the text has a fence that names the block, written exactly or not."""
    return bool(LOOSE.search(issue.replace("\r\n", "\n").replace("\r", "\n"))) if isinstance(issue, str) else False


def digest(examples):
    return hashlib.sha256(json.dumps(examples, sort_keys=True).encode("utf-8")).hexdigest()


def no_runner(cfg, name):
    """True when the job's environment runs something other than Python (vitest): the harness has no example runner there and
    records that instead of asking for examples it cannot run."""
    env = (((cfg or {}).get("sandbox") or {}).get("environments") or {}).get(name) if name else None
    return bool(env) and ct.runner(env) != "pytest"


# ---- what is stored ---------------------------------------------------------------------------------------------------

def intake_key(snapshot_sha256, examples):
    return hashlib.sha256(f"examples-intake\n{snapshot_sha256}\n{digest(examples)}".encode("utf-8")).hexdigest()


def audit_key(patch_sha256, examples):
    return hashlib.sha256(f"examples-audit\n{patch_sha256}\n{digest(examples)}".encode("utf-8")).hexdigest()


def _write(path, rec):
    """Atomically: a process that dies leaves the earlier file (the pending marker) and never half of a new one."""
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(rec), encoding="utf-8")
    os.replace(tmp, path)


def store(path, key, *, results=None, skipped=None, reason=None):
    """results None and no `skipped` is the pending marker (`reason`: why the last run did not finish). Raises when it cannot
    write: a caller that needs the marker must not go on without it."""
    _write(path, {"key": key, "skipped": skipped, "results": results, "reason": reason})


def _result(raw, ids):
    """One stored result read back with every text cleaned again (the file can be edited), or None if it is not one."""
    if not isinstance(raw, dict) or raw.get("id") not in ids or raw.get("status") not in STATUSES:
        return None
    out = {"id": raw["id"], "tier": raw.get("tier") if raw.get("tier") in ex.TIERS else "same", "status": raw["status"]}
    for k in ("actual", "base_actual"):
        if k in raw:
            out[k] = ex.shown(raw[k])
    return out


def load(path, key, examples):
    """('none', None) no file; ('stale', None) the file is for another patch or other examples; ('skipped', why);
    ('pending', reason or None) a run that did not finish; ('error', None) a damaged file or results that are not exactly the
    examples'; ('results', [result]) a finished run. Whatever else is wrong with a file reads as 'error', never as a pass."""
    try:
        path = Path(path)
        if not path.exists():
            return "none", None
        rec = json.loads(path.read_text(encoding="utf-8"))
        if rec.get("key") != key:
            return "stale", None
        if rec.get("skipped"):
            return "skipped", ex.clean(str(rec["skipped"]), 200)
        if rec.get("results") is None:
            return "pending", ex.clean(str(rec["reason"]), 200) if rec.get("reason") else None
        ids = {e["id"] for e in examples}
        results = [_result(r, ids) for r in rec["results"]]
        if any(r is None for r in results) or sorted(r["id"] for r in results) != sorted(ids):
            return "error", None
        return "results", results
    except Exception:
        return "error", None


def failing(results):
    """The ids of the results that are not a pass (an unchecked one counts: the audit runs everything)."""
    return sorted(r["id"] for r in results if r["status"] != ex.PASS)


# ---- running ----------------------------------------------------------------------------------------------------------

def _expected(e):
    return f"raises {e['raises']}" if "raises" in e else "expects " + ex.clean(json.dumps(e["expect"], sort_keys=True), 120)


def _holders(tree, example):
    """Other modules of the tree that hold the name an override sets (so the writer sees where the value is really read)."""
    out = []
    for name in (example.get("overrides") or {}):
        module, _, attr = name.rpartition(".")
        mine = module.replace(".", "/") + ".py"
        pat = re.compile(rf"^{re.escape(attr)}\s*=", re.M)
        for dirpath, dirs, files in os.walk(tree):
            dirs[:] = sorted(d for d in dirs if not d.startswith("."))[:200]
            for f in sorted(files):
                rel = os.path.relpath(os.path.join(dirpath, f), tree)
                if f.endswith(".py") and not rel.endswith(mine):
                    try:
                        with open(os.path.join(dirpath, f), encoding="utf-8", errors="replace") as fh:
                            if pat.search(fh.read(200_000)):
                                out.append(rel)
                    except OSError:
                        pass
                if len(out) >= HOLDERS_MAX:
                    return out
    return out


class NoResult(SandboxUnavailable):
    """A pass in which no example printed anything: the container failed, OR the code of an example killed its own process. The
    intake and the audit treat it as an unavailable sandbox; a writer's gate turns it into a rejection (a model cannot end its own
    job by writing an example that kills the pass)."""


def _no_pass_ran(results):
    """True when no example of a pass printed a result at all: the container failed (a missing image, a docker error, a timeout of
    the whole pass), which says nothing about the examples."""
    return bool(results) and all(isinstance(r.get("actual"), str) and r["actual"].startswith(ex.E_NORESULT) for r in results)


def check_base(examples, tree, runner, root=BOX_ROOT):
    """(results, problems) of the examples run on the base tree (`tree` is the host path, for the tautology check; `root` is
    where the runner sees it). `same` must pass; `whatif` must pass with its overrides and must not give the same result
    without them (an override that changes nothing proves nothing); `after` is run for information and must not already
    pass (then it is a `same`). A SandboxUnavailable of the runner is not caught: it is not a problem of the examples."""
    problems, bad = [], set()
    for e in examples:
        why = ex.tautology_problem(e, tree)
        if why:
            problems.append(why)
            bad.add(e["id"])
    runnable = [e for e in examples if e["id"] not in bad]
    results = []
    if not runnable:
        return results, problems
    evaluated = ex.evaluate(runnable, runner, root=root)
    if _no_pass_ran(evaluated):
        raise NoResult("the pass printed no result")
    got = {r["id"]: r for r in evaluated}
    whatif = [e for e in runnable if e["tier"] == "whatif"]
    bare = ex.run_pass(whatif, runner, root=root, with_overrides=False) if whatif else {}
    if whatif and _no_pass_ran([{"actual": r.get("error", "") + ""} for r in bare.values()]):
        raise NoResult("the pass without overrides printed no result")
    for e in runnable:
        r = got[e["id"]]
        if e["tier"] == "after":
            if r["status"] == ex.PASS:
                problems.append(f"example {e['id']} (after) already passes on the base: it is a `same` example, not new behaviour")
            results.append({"id": e["id"], "tier": "after", "status": ex.UNCHECKED, "base_actual": r["actual"]})
            continue
        results.append(r)
        if r["status"] != ex.PASS:
            problems.append(f"example {e['id']} ({e['tier']}) {r['status']}: {_expected(e)}; the code gave "
                            f"{ex.clean(json.dumps(r['actual'], sort_keys=True), 200)}")
        elif e["tier"] == "whatif":
            b = ex.verdict(e, bare[e["id"]])
            if (b["status"], json.dumps(b["actual"], sort_keys=True)) == (r["status"], json.dumps(r["actual"], sort_keys=True)):
                held = _holders(tree, e)
                problems.append(f"example {e['id']} (whatif): the override changes nothing the example sees (the value is read "
                                "by value at import, or as a default argument)"
                                + (f"; other modules that set the name: {', '.join(held)}" if held else ""))
    return results, problems


def audit(examples, runner, root=BOX_ROOT):
    """[{id, tier, status, actual}] of every example on the tree with the patch applied: `whatif` without its overrides (the
    constant has changed now; the example asserts the behaviour), and `after` like any other."""
    results = ex.evaluate(examples, runner, root=root, with_overrides=False)
    if _no_pass_ran(results):
        raise NoResult("the pass printed no result")
    return results


# ---- what a human reads -----------------------------------------------------------------------------------------------

def _show(value, limit=80):
    return ex.clean(value if isinstance(value, str) else json.dumps(value, sort_keys=True), limit)


def intake_lines(state):
    """Lines for status and the approve screen from load(): what the examples did on the base."""
    kind, val = state
    if kind == "skipped":
        return [f"examples at base: not run ({val})"]
    if kind != "results":
        return {"stale": ["examples at base: not run for this issue or base"],
                "error": ["examples at base: the stored result cannot be read"]}.get(kind, [])
    parts = []
    for r in val:
        if r["status"] == ex.UNCHECKED:
            parts.append(f"{r['id']} after: gives {_show(r.get('base_actual'))} now (not checked before the change)")
        else:
            parts.append(f"{r['id']} {r['tier']}: {r['status']}" + ("" if r["status"] == ex.PASS else f" ({_show(r['actual'])})"))
    return ["examples at base: " + "; ".join(parts) + f" {ex.RUN_LABEL}"]


def audit_lines(state, job_id):
    """Lines for status from load(): the examples on the patched tree, and what apply will do about them."""
    kind, val = state
    if kind == "skipped":
        return [f"examples after the agent: not run ({val})"]
    if kind == "pending":
        return ["examples after the agent: NOT FINISHED" + (f" ({val})" if val else "")
                + f"; `argus apply` refuses it: `argus resume {job_id}` runs it again"]
    if kind in ("none", "stale", "error"):
        return [{"none": "examples after the agent: no result", "stale": "examples after the agent: the result is for another patch",
                 "error": "examples after the agent: the stored result cannot be read"}[kind]
                + f"; `argus apply` refuses it: `argus resume {job_id}` runs it again"]
    bad = failing(val)
    parts = [f"{r['id']} {r['tier']}: {r['status']}" + ("" if r["status"] == ex.PASS else f" ({_show(r['actual'])})") for r in val]
    line = "examples after the agent: " + "; ".join(parts) + f" {ex.RUN_LABEL}"
    if bad:
        return [line, f"examples failed: {', '.join(bad)}; `argus apply` refuses unless you give --allow-failed-examples {','.join(bad)}"]
    return [line]
