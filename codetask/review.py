"""The review package (M6 W3): after a run is DONE, a deterministic, model-free summary a human can review and turn
into a pull request. Nothing here asks a model anything or trusts what the agent said.

  <run>/review/
    changes.patch     a git patch from the base commit's tree to the agent's final workspace (SUMMARY.json
                      excluded). For a task it also adds the approved new tests and changes the approved changed
                      tests (W2a-ext), so it is the whole pull request.
    tests.md          each criterion of the verdict, and every validation run again, fresh, on base commit + patch
    claims.md         the agent's claims with the harness's verdict on each, its free-text summary (not evidence),
                      and what was never verified automatically
    provenance.json   repository, base commit, Argus commit, contract sha256, models, cost from the ledger, the
                      patch hash and every check below with its result
    PR.md             a draft of the pull request description

How the patch is made. The base commit's tree is rebuilt from the repository (the same function intake used, so
.gitattributes cannot change a byte), copied into a fresh git repository with one commit, and mirrored to the final
workspace: every file is deleted, the final workspace is copied in, and `git diff --cached --binary --full-index`
gives the patch. So a new, changed or deleted file, a mode change and a binary file are all represented. Git runs
without user or system config and without hooks, and with attributes switched off (-text -ident -filter) so nothing
converts a byte; no code of the repository is run.

What is checked, and the package is `valid` only if every check passes (otherwise it is written with the reasons and
PR.md says NOT READY at the top):
  - the run is DONE and its frozen contract is unchanged;
  - the last verdict passed and holds for exactly the final workspace (its workspace digest), and the SUMMARY.json
    that is published is the very one (same bytes, read once) the verdict saw;
  - the input repository still is what the run started from (digest and intake record);
  - the base commit rebuilt from the repository, plus the task's approved new tests and changed tests, is that input exactly;
  - what the agent changed is inside the writable scope (never protected, never an intake exclusion) and is exactly
    the verdict's own list of changed files;
  - the patch applies to a clean rebuild of the base commit, and the result is identical to the final workspace in
    every file (path, content, executable bit), also the files nobody changed;
  - every validation of the contract, run again on that patched tree in the sandbox, gives the verdict's result;
  - the workspace is still exactly what the verdict saw when all of that is done (it was not written into meanwhile).

Limit: the package is exact at the level of the committed bytes. A repository whose .gitattributes converts line
endings or filters files at checkout can show the same patch differently in a reviewer's working tree; that is not
detected here (Argus has no .gitattributes).

The package is written to a temporary directory and renamed, and an existing package is never overwritten. It
holds no timestamps, so building it twice gives the same bytes.
"""
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tempfile
from pathlib import Path

from acceptance import contract as ct
from acceptance import intake
from acceptance.claims import schema_problems
from acceptance.contract import SUMMARY, claims_schema, matches
from acceptance.validation import run_validation
from acceptance.workspace import SPECIAL, diff, digest, snapshot
from harness.events import parse_lines
from harness.llm import reconcile_ledger

from . import frozen

DIR = "review"
FILES = ("changes.patch", "tests.md", "claims.md", "provenance.json", "PR.md")
VERSION = 1
# options for every git call: nothing converts a byte, and the file mode is kept
GIT = ("-c", "core.autocrlf=false", "-c", "core.safecrlf=false", "-c", "core.fileMode=true",
       "-c", "core.quotepath=true", "-c", "commit.gpgsign=false", "-c", "user.name=argus", "-c", "user.email=argus@invalid")
NO_ATTRIBUTES = "* -text -ident -filter\n"        # beats the repository's own .gitattributes: no byte is converted
COMPARED = ("outcome", "tests_run", "failures", "errors", "skipped")      # evidence a fresh validation must repeat


class ReviewError(Exception):
    pass


class Checks:
    def __init__(self):
        self.items = []

    def add(self, id, ok, detail=""):
        self.items.append({"id": id, "ok": bool(ok), "detail": "" if ok else detail})   # a passing check says nothing
        return bool(ok)

    def skip(self, id, why):
        self.items.append({"id": id, "ok": False, "detail": f"not run: {why}"})

    @property
    def valid(self):
        return all(c["ok"] for c in self.items)

    @property
    def problems(self):
        return [f"{c['id']}: {c['detail']}" for c in self.items if not c["ok"]]


# ---- file trees ------------------------------------------------------------------------------------------------

def tree_state(root, skip_cache=False):
    """{path: (sha256, executable)} for every file below root. The executable bit only exists on posix."""
    out = {}
    for path, h in snapshot(root, skip_cache=skip_cache).items():
        x = os.name == "posix" and h != SPECIAL and bool(os.lstat(Path(root) / path).st_mode & stat.S_IXUSR)
        out[path] = (h, x)
    return out


def state_diff(a, b):
    return {"added": sorted(set(b) - set(a)), "removed": sorted(set(a) - set(b)),
            "modified": sorted(p for p in set(a) & set(b) if a[p] != b[p])}


def _changed(d):
    return sorted(d["added"] + d["removed"] + d["modified"])


def rebuild_base(repo, record, dest):
    """The base commit's tree minus the intake's exclusions, written below dest (which must exist and be empty)."""
    intake.write_tree(repo, record["commit"], Path(dest), record["exclude"])


def _clear(path):
    """Remove a directory tree, also the read-only object files git writes (on Windows they block rmtree)."""
    def retry(fn, p, *_):
        os.chmod(p, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
        fn(p)
    shutil.rmtree(path, **({"onexc": retry} if sys.version_info >= (3, 12) else {"onerror": retry}))


def make_patch(base_dir, final_dir, work):
    """The patch from base_dir's files to final_dir's (SUMMARY.json left out), as bytes. Both stay untouched."""
    repo = Path(work) / "mirror"
    shutil.copytree(base_dir, repo, symlinks=True)
    g = lambda *a, **k: intake.git(repo, *GIT, *a, **k)   # noqa: E731
    intake.git(repo, "init", "-q")
    (repo / ".git" / "info").mkdir(exist_ok=True)
    (repo / ".git" / "info" / "attributes").write_text(NO_ATTRIBUTES, encoding="utf-8")
    g("add", "-A", "-f")
    g("commit", "-q", "-m", "base")
    for entry in repo.iterdir():                      # the mirror: whatever the base has and the final has not goes
        if entry.name != ".git":
            _clear(entry) if entry.is_dir() and not entry.is_symlink() else entry.unlink()
    final_dir = Path(final_dir)
    shutil.copytree(final_dir, repo, symlinks=True, dirs_exist_ok=True,
                    ignore=lambda d, names: [SUMMARY] if Path(d) == final_dir else [])
    g("add", "-A", "-f")
    return g("diff", "--cached", "--binary", "--full-index", "--no-renames", "--no-color", "--no-ext-diff")


def apply_patch(patch_file, repo, record, dest):
    """Rebuild the base commit below dest and apply the patch exactly as a reviewer would. dest is left without .git."""
    dest = Path(dest)
    dest.mkdir(parents=True)
    rebuild_base(repo, record, dest)
    intake.git(dest, "init", "-q")
    (dest / ".git" / "info").mkdir(exist_ok=True)
    (dest / ".git" / "info" / "attributes").write_text(NO_ATTRIBUTES, encoding="utf-8")
    intake.git(dest, *GIT, "apply", "--check", "--whitespace=nowarn", str(Path(patch_file).resolve()))
    intake.git(dest, *GIT, "apply", "--whitespace=nowarn", str(Path(patch_file).resolve()))
    _clear(dest / ".git")


# ---- the run's evidence -----------------------------------------------------------------------------------------

def _read_json(path, what):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ReviewError(f"{what} ({path}) is unreadable: {e}") from e


def ledger(run_dir):
    events = parse_lines((Path(run_dir) / "events.jsonl").read_text(encoding="utf-8")) \
        if (Path(run_dir) / "events.jsonl").exists() else []
    _, totals = reconcile_ledger(events)
    models = sorted({e["model"] for e in events if e.get("event") == "llm_call_started" and e.get("model")})
    return totals, models


def _same_validation(spec, verdict_c, fresh):
    """Problems between the verdict's criterion of a validation and the same validation run again."""
    if fresh["status"] != "pass":
        return [f"{spec['id']}: fresh run is {fresh['status']}: {fresh.get('reason')}"]
    if verdict_c is None:
        return [f"{spec['id']}: the verdict has no such criterion"]
    problems = []
    if verdict_c["status"] != fresh["status"]:
        problems.append(f"{spec['id']}: verdict {verdict_c['status']}, fresh {fresh['status']}")
    a, b = verdict_c.get("evidence") or {}, fresh.get("evidence") or {}
    for k in COMPARED + ("must_pass",):
        if a.get(k) != b.get(k):
            problems.append(f"{spec['id']}: {k} was {a.get(k)!r} in the verdict, {b.get(k)!r} fresh")
    return problems


def read_summary_once(ws, schema):
    """(document, sha256, problems) from ONE read of SUMMARY.json: the text that is published and the hash that is
    checked are the same bytes."""
    path = Path(ws) / SUMMARY
    try:
        if path.is_symlink() or not path.is_file():
            return None, None, [f"{SUMMARY} is not a regular file"]
        raw = path.read_bytes()
        doc = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError) as e:
        return None, None, [f"{SUMMARY} is unreadable: {e}"]
    return doc, hashlib.sha256(raw).hexdigest(), schema_problems(doc, schema)


# ---- the checks -------------------------------------------------------------------------------------------------

def verify(run_dir, result, *, repo, sandbox_cfg, root, validate, work):
    """Run every check. Returns (checks, facts, patch bytes or None)."""
    run_dir, root, ck = Path(run_dir), Path(root), Checks()
    facts = {"patch": None, "files": [], "fresh": {}, "verdict": None, "contract": None, "record": None,
             "summary": None}
    ws = run_dir / "workspace"
    try:
        contract = frozen.load(run_dir, result["contract_sha"])
        ck.add("contract_frozen", True)
    except (frozen.ContractChanged, KeyError, ValueError) as e:
        ck.add("contract_frozen", False, str(e))
        return ck, facts, None
    facts["contract"] = contract

    iteration = (result.get("verdict") or {}).get("iteration")
    verdict_path = run_dir / f"verdict_{iteration}.json"
    try:
        verdict = _read_json(verdict_path, "the last verdict")
    except ReviewError as e:
        ck.add("verdict_passed", False, str(e))
        return ck, facts, None
    facts["verdict"] = verdict
    final = tree_state(ws) if ws.is_dir() else None
    problems = []
    if verdict.get("outcome") != "pass":
        problems.append(f"the last verdict is {verdict.get('outcome')!r}")
    if final is None:
        problems.append("the run's workspace is missing")
    elif verdict.get("workspace_digest") != digest(snapshot(ws)):
        problems.append("the workspace is not the one the verdict was reached on (digest differs)")
    elif (result.get("verdict") or {}).get("workspace_digest") != verdict.get("workspace_digest"):
        problems.append("result.json and the verdict disagree on the workspace digest")
    if not ck.add("verdict_passed", not problems, "; ".join(problems)):
        return ck, facts, None
    doc, summary_sha, problems = read_summary_once(ws, claims_schema(contract))
    if summary_sha != verdict.get("summary_sha256"):
        problems.append(f"{SUMMARY} is not the one the verdict was reached on")
    if not ck.add("summary_bound", not problems, "; ".join(problems)):
        return ck, facts, None
    facts["summary"] = doc

    # the input the run started from
    prov = (result.get("provenance") or {}).get("input") or {}
    pristine_dir = root / (prov.get("workspace") or "")
    try:
        record = intake.record_for(prov.get("workspace") or "", root)
    except intake.IntakeError as e:
        ck.add("input_unchanged", False, str(e))
        return ck, facts, None
    if record is None:
        ck.add("input_unchanged", False, "the input has no intake record, so no base commit is known: a review "
               "package needs an intake (scripts/intake_repo.py)")
        return ck, facts, None
    facts["record"] = record
    if not pristine_dir.is_dir():
        ck.add("input_unchanged", False, f"the input repository {pristine_dir} is missing")
        return ck, facts, None
    problems = intake.check(record, pristine_dir)
    pristine = tree_state(pristine_dir, skip_cache=True)
    if digest(snapshot(pristine_dir, skip_cache=True)) != prov.get("snapshot_sha256"):
        problems.append("the input differs from what the run started from (snapshot hash)")
    if not ck.add("input_unchanged", not problems, "; ".join(problems)):
        return ck, facts, None

    # the base commit
    approved = dict(record.get("added") or {})
    changed_tests = record.get("changed") or {}           # W2a-ext: existing tests the approved task changed
    with tempfile.TemporaryDirectory(dir=work) as tmp:
        base_dir = Path(tmp) / "base"
        base_dir.mkdir()
        try:
            rebuild_base(repo, record, base_dir)
            base_commit_tree = intake.git(repo, "rev-parse", "--verify", f"{record['commit']}^{{tree}}").decode().strip()
        except (intake.IntakeError, OSError) as e:
            ck.add("base_commit", False, f"the base commit {record['commit'][:12]} cannot be rebuilt from {repo}: {e}")
            return ck, facts, None
        base = tree_state(base_dir)
        expected = dict(base)
        problems = [f"approved new test {p} already exists in the base commit" for p in sorted(approved) if p in base]
        for p, h in approved.items():
            expected[p] = (h, False)
        for p, c in sorted(changed_tests.items()):
            if base.get(p, (None,))[0] != c.get("before"):
                problems.append(f"approved changed test {p} is not, in the base commit, the version it was changed from")
            expected[p] = (c.get("after"), False)
        approved.update({p: c.get("after") for p, c in changed_tests.items()})
        if base_commit_tree != record.get("tree"):
            problems.append(f"the commit's tree is {base_commit_tree[:12]}, the intake recorded {str(record.get('tree'))[:12]}")
        extra = state_diff(expected, pristine)
        if _changed(extra):
            problems.append("the input is not the base commit plus the approved new and changed tests: "
                            + json.dumps(extra, sort_keys=True)[:400])
        if SUMMARY in pristine:
            problems.append(f"the input already contains {SUMMARY}, which the run uses for its own claims")
        if not ck.add("base_commit", not problems, "; ".join(problems)):
            return ck, facts, None

        # what the agent changed
        agent = state_diff(pristine, final)
        changed = [p for p in _changed(agent) if p != SUMMARY]
        sc = contract["scope"]
        problems = []
        for p in changed:
            if ".git" in p.split("/"):
                problems.append(f"{p} is inside a .git directory")
            elif matches(p, sc["protected"]):
                problems.append(f"{p} is protected")
            elif not matches(p, sc["writable"]):
                problems.append(f"{p} is outside the writable scope")
            elif intake.excluded(p, record["exclude"]):
                problems.append(f"{p} is a path the intake excluded")
        special = sorted(p for p, (h, _) in final.items() if h == SPECIAL)
        problems += [f"{p} is not a regular file" for p in special]
        ck.add("changes_in_scope", not problems, "; ".join(problems))
        if problems:
            return ck, facts, None
        listed = next((c for c in verdict["criteria"] if c["id"] == "scope:protected"), None)
        theirs = ((listed or {}).get("evidence") or {}).get("diff")
        sha_only = diff({p: v[0] for p, v in pristine.items()}, {p: v[0] for p, v in final.items()})
        mine = {k: [p for p in v if p != SUMMARY] for k, v in sha_only.items()}
        theirs = {k: [p for p in v if p != SUMMARY] for k, v in (theirs or {}).items()}
        same = mine == theirs and sorted(changed) == sorted(_changed(mine))
        if not ck.add("changes_match_verdict", same, f"the verdict lists {theirs}, the workspace differs by "
                      f"{sorted(changed)}"):
            return ck, facts, None
        if not changed:
            ck.add("has_changes", False, "the agent changed nothing")
            return ck, facts, None

        # the patch
        patch_dir = Path(tmp) / "mirror_work"
        patch_dir.mkdir()
        try:
            patch = make_patch(base_dir, ws, patch_dir)
        except (intake.IntakeError, OSError) as e:
            ck.add("patch_made", False, str(e))
            return ck, facts, None
        if not ck.add("patch_made", bool(patch.strip()), "the patch is empty"):
            return ck, facts, None
        facts["patch"] = patch
        patch_file = Path(tmp) / "changes.patch"
        patch_file.write_bytes(patch)
        applied = Path(tmp) / "applied"
        try:
            apply_patch(patch_file, repo, record, applied)
        except (intake.IntakeError, OSError) as e:
            ck.add("patch_applies", False, f"git apply on the base commit failed: {e}")
            return ck, facts, None
        ck.add("patch_applies", True)
        want = {p: v for p, v in final.items() if p != SUMMARY}
        got = tree_state(applied)
        d = state_diff(want, got)
        ck.add("final_state_identical", not _changed(d),
               "base commit + patch differs from the final workspace: " + json.dumps(d, sort_keys=True)[:400])
        from_base = state_diff(base, got)
        facts["files"] = sorted(
            [{"path": p, "change": c, "approved_test": p in approved and got.get(p, (None,))[0] == approved[p]}
             for c, ps in (("A", from_base["added"]), ("M", from_base["modified"]), ("D", from_base["removed"]))
             for p in ps], key=lambda f: f["path"])
        if _changed(d):
            return ck, facts, patch

        # every validation again, on the tree a reviewer gets
        problems = []
        for spec in contract["validation"]:
            fresh = validate(spec, str(applied), sandbox_cfg)
            facts["fresh"][spec["id"]] = fresh
            vc = next((c for c in verdict["criteria"] if c["id"] == f"validation:{spec['id']}"), None)
            problems += _same_validation(spec, vc, fresh)
        ck.add("revalidation_matches", not problems, "; ".join(problems))
        # nothing was written into the run's workspace while all of the above ran: the package describes the
        # state the verdict was reached on, not a later one
        ck.add("workspace_stable", digest(snapshot(ws)) == verdict["workspace_digest"],
               "the workspace changed while the package was being built")
    return ck, facts, patch


# ---- rendering --------------------------------------------------------------------------------------------------

def fence(text, lang=""):
    """A fenced block that nothing inside the text can close."""
    text = "".join(c for c in str(text) if c in "\n\t" or ord(c) >= 32)
    longest = max([len(m) for m in re.findall(r"`+", text)] + [2])
    bar = "`" * (longest + 1)
    return f"{bar}{lang}\n{text}\n{bar}"


def cell(text, limit=160):
    t = " ".join(str(text if text is not None else "").split())
    t = t.replace("|", "\\|")
    return t if len(t) <= limit else t[:limit - 3] + "..."


def _status(c):
    return c["status"] if c else "-"


def render_tests(contract, verdict, fresh):
    out = ["# Validation", "",
           "**Verdict**: what acceptance recorded at the end of the run, in the run's workspace.  ",
           "**Fresh**: the same validation run again in the sandbox on a clean tree built from the base commit and "
           "`changes.patch`, which is the tree a reviewer gets.", "",
           "| Criterion | Layer | Verdict | Fresh |", "|---|---|---|---|"]
    for c in verdict["criteria"]:
        spec_id = c["id"].split(":", 1)[1] if c["id"].startswith("validation:") else None
        out.append(f"| {cell(c['id'])} | {c['layer']} | {c['status']} | {fresh[spec_id]['status'] if spec_id in fresh else '-'} |")
    for spec in contract["validation"]:
        f = fresh.get(spec["id"])
        v = next((c for c in verdict["criteria"] if c["id"] == f"validation:{spec['id']}"), None)
        out += ["", f"## validation `{spec['id']}`", "", f"`{' '.join([spec['executable'], *spec['args']])}`"]
        if spec.get("environment"):
            out.append(f"sandbox environment: `{spec['environment']}`")
        out += ["", "| | Verdict | Fresh |", "|---|---|---|"]
        for k in ("status",) + COMPARED:
            a = (v or {}).get("status") if k == "status" else ((v or {}).get("evidence") or {}).get(k)
            b = (f or {}).get("status") if k == "status" else ((f or {}).get("evidence") or {}).get(k)
            out.append(f"| {k} | {cell(a)} | {cell(b)} |")
        if spec.get("must_pass"):
            va = ((v or {}).get("evidence") or {}).get("must_pass") or {}
            fb = ((f or {}).get("evidence") or {}).get("must_pass") or {}
            out += ["", "| Required test | Verdict | Fresh |", "|---|---|---|"]
            out += [f"| `{cell(n, 200)}` | {cell(va.get(n))} | {cell(fb.get(n))} |" for n in spec["must_pass"]]
        if f is None:
            out += ["", "_not run again_"]
    return "\n".join(out) + "\n"


def render_claims(contract, verdict, doc, record):
    out = ["# Claims", "",
           "The agent's structured claims, each with the harness's verdict from its own evidence. A claim the "
           "evidence does not support fails acceptance, so a DONE run has none of those.", "",
           "| # | Claim | Evidence | Verdict | Reason |", "|---|---|---|---|---|"]
    checked = {c["id"]: c for c in verdict["criteria"] if c["layer"] == "D"}
    claims = (doc or {}).get("claims") or []
    for i, c in enumerate(claims):
        v = checked.get(f"claim[{i}]:{c.get('claim')}")
        out.append(f"| {i} | {cell(c.get('claim'))} | {cell(c.get('evidence') or c.get('path'))} | {_status(v)} | "
                   f"{cell((v or {}).get('reason'))} |")
    if not claims:
        out.append("| | _the agent claimed nothing_ | | | |")
    out += ["", "## Agent's summary", "", "Free text from the agent. It is **not evidence** and nothing in it was "
            "checked.", "", fence((doc or {}).get("summary") or "(none)")]
    notes = (record or {}).get("unverifiable") or []
    out += ["", "## Not verified automatically", ""]
    out += (["Recorded when the task was approved. None of these is a passing criterion; a reviewer has to check "
             "them.", ""] + [f"- {cell(n, 500)}" for n in notes]) if notes else ["Nothing was recorded."]
    return "\n".join(out) + "\n"


def render_pr(prov, contract, record, doc, ck):
    issue = (contract.get("inputs") or {}).get("issue") or ""
    first = (issue.strip().splitlines() or [""])[0].strip()
    if len(first) <= 80:
        short = first
    else:
        head = first[:81]
        at = head.rfind(" ")
        kept = head[:at].rstrip(" ") if at != -1 else ""
        short = (kept if kept else first[:80]) + "..."
    title = f"{contract['contract']}: " + short
    out = []
    if not ck.valid:
        out += ["> **NOT READY: this package failed its own verification. Do not open a PR from it.**", ">"]
        out += [f"> - {cell(p, 400)}" for p in ck.problems] + [""]
    out += [f"# {cell(title, 120)}", "", "## Issue", "", fence(issue), "", "## What changed", ""]
    out += [f"- `{f['change']}` `{f['path']}`" + ((" (new test, approved with the task)" if f["change"] == "A" else
                                                    " (changed test, approved with the task)")
                                                   if f["approved_test"] else "")
            for f in prov["patch"]["files"]] or ["_no patch_"]
    changed = (record or {}).get("changed") or {}
    if changed:                                               # W2a-ext
        out += ["", "## Existing tests changed by the task", "",
                "Approved with the task, before the agent ran (the agent cannot change them). Their diff is in "
                "`changes.patch`: read it, a changed test can be weaker than the old one.", ""]
        for p, c in sorted(changed.items()):
            out.append(f"- `{cell(p)}`")
            out += [f"  - removed `{cell(r['node'])}`: {cell(r['reason'], 500)}" for r in c.get("removed") or []]
            out += [f"  - modified `{cell(m['node'])}`: {cell(m['reason'], 500)}" for m in c.get("modified") or []]
    out += ["", "## Validation", "", "Every validation was run again in the sandbox on the base commit plus "
            "`changes.patch` (see `tests.md`):", ""]
    out += [f"- `{k}`: {v}" for k, v in prov["validation_fresh"].items()] or ["- not run"]
    if (record or {}).get("feasibility") == "unproven":       # W2b: approved without a reference patch
        out += ["", "The task was approved without a reference patch (feasibility: unproven): before this run, no "
                "solution had shown that its criteria can be met, and its new tests were drafted, not proven right. "
                "Read the tests as well as the change."]
    out += ["", "## Checks on this package", ""]
    out += [f"- {'ok' if c['ok'] else 'FAILED'}: `{c['id']}`" + ("" if c["ok"] else f" - {cell(c['detail'], 300)}")
            for c in prov["checks"]]
    notes = (record or {}).get("unverifiable") or []
    if notes:
        out += ["", "## Not verified automatically", ""] + [f"- {cell(n, 500)}" for n in notes]
    out += ["", "## Agent's summary (not evidence)", "", fence(((doc or {}).get("summary")) or "(none)"), "",
            "## How to apply", "",
            fence(f"git checkout -b <branch> {prov['base']['commit']}\ngit apply --whitespace=nowarn changes.patch", "sh"),
            "", "## Provenance", "",
            f"- base: `{prov['base']['repo']}` at `{prov['base']['commit']}`",
            f"- Argus: `{(prov['argus'] or {}).get('commit')}`" + (" **(tracked files had local changes)**"
                                                                 if (prov["argus"] or {}).get("dirty") else ""),
            f"- contract: `{prov['contract']['name']}` sha256 `{prov['contract']['sha256']}`",
            f"- models: {', '.join(prov['models']) or 'none'}; {prov['cost']['calls']} calls, "
            f"${prov['cost']['usd']:.6f}" + ("" if prov["cost"]["usd_complete"] else " (incomplete: unpriced calls)"),
            f"- run: `{prov['run_id']}`, {prov['attempts']} attempt(s); patch sha256 `{prov['patch']['sha256']}`", "",
            "## Outcome of the pilot", "",
            "Set by the reviewer, not by Argus: **agent-completed** if the patch is applied unchanged and the "
            "independent validation and `verify.sh` pass; **human-assisted** if you change any file in it (keep "
            "that change as its own diff); **failed** otherwise. Editing this description is supervision time, not "
            "a change of status."]
    return "\n".join(out) + "\n"


# ---- the package ------------------------------------------------------------------------------------------------

def build(run_dir, *, repo, sandbox_cfg, root=".", validate=run_validation):
    """Build <run_dir>/review/ for a DONE run. Returns {"valid", "problems", "dir"}. Raises ReviewError when there is
    nothing to build (the run is not DONE, no result) or a package already exists."""
    run_dir = Path(run_dir)
    out = run_dir / DIR
    if out.exists():
        raise ReviewError(f"{out} already exists; a package is never overwritten (remove it to build again)")
    result = _read_json(run_dir / "result.json", "the run's result")
    if result.get("status") != "DONE":
        raise ReviewError(f"the run is {result.get('status')}, not DONE: only a DONE run has a review package")
    stage = Path(tempfile.mkdtemp(dir=run_dir, prefix=".review-"))
    try:
        with tempfile.TemporaryDirectory() as work:
            ck, facts, patch = verify(run_dir, result, repo=repo, sandbox_cfg=sandbox_cfg, root=root,
                                      validate=validate, work=work)
        contract, verdict, record = facts["contract"], facts["verdict"], facts["record"]
        totals, models = ledger(run_dir)
        prov_in = (result.get("provenance") or {})
        doc = facts["summary"]            # read once, in verify(), and bound to the verdict's hash
        patch_info = {"sha256": hashlib.sha256(patch).hexdigest() if patch else None,
                      "bytes": len(patch) if patch else 0, "files": facts["files"]}
        prov = {"package_version": VERSION, "valid": ck.valid, "problems": ck.problems, "checks": ck.items,
                "run_id": result.get("run_id"), "attempts": result.get("attempts"),
                "contract": {"name": (contract or {}).get("contract"), "sha256": result.get("contract_sha")},
                "input": prov_in.get("input"), "argus": prov_in.get("argus"),
                "base": {"repo": (record or {}).get("repo"), "commit": (record or {}).get("commit"),
                         "tree": (record or {}).get("tree")},
                "models": models, "cost": {"calls": totals["calls"], "usd": totals["usd"], "usd_nano": totals["usd_nano"],
                                           "usd_complete": totals["usd_complete"],
                                           "unknown_after_crash": totals["unknown_after_crash"]},
                "verdict": None if verdict is None else {k: verdict.get(k) for k in
                                                          ("outcome", "workspace_digest", "verdict_sha256")},
                "patch": patch_info,
                "validation_fresh": {k: v["status"] for k, v in facts["fresh"].items()}}
        files = {"provenance.json": (json.dumps(prov, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode(),
                 "PR.md": render_pr(prov, contract or {"contract": "?", "inputs": {}}, record, doc, ck).encode()}
        if patch:
            files["changes.patch"] = patch
        if contract is not None and verdict is not None:
            files["tests.md"] = render_tests(contract, verdict, facts["fresh"]).encode()
            files["claims.md"] = render_claims(contract, verdict, doc, record).encode()
        for name, data in files.items():
            (stage / name).write_bytes(data)
        os.replace(stage, out)
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return {"valid": ck.valid, "problems": ck.problems, "dir": str(out)}
