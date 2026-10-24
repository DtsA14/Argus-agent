"""Grade a router job's review package SWE-bench style (docs/reviews/SPEC_SWE_PILOT.md 2.3). No model call.

  python scripts/swe_grade.py --instance ~/swe/inst/<id> --repo ~/swe/<repo> --review <review dir> --sha <sha256> \
      --environment sympy --out grade.json

The instance directory holds base_commit.txt, test_patch.diff, patch.diff (the maintainers' fix), FAIL_TO_PASS.txt and
PASS_TO_PASS.txt (JSON lists of test names). The steps, as the official harness takes them:
  1. the patch graded is the review package's: sha256 of changes.patch == --sha == provenance.json patch.sha256;
  2. the commit's tree (intake.write_tree: no .git) plus changes.patch;
  3. every file test_patch touches back to its base_commit content (or removed if it was not there), then test_patch:
     the official tests win over any change the agent or the drafter made to the same files;
  4. the tests of test_patch's files run in the sandbox environment; a name is mapped to `file::name` in those files,
     and one found in no file or in two is `missing`;
  5. per node pass / fail / missing; resolved = every FAIL_TO_PASS and every PASS_TO_PASS node found and passing.
Also, for information only (not part of resolved): the tests approved with the task, run on base_commit plus the
maintainers' fix. Exit codes: 0 graded (resolved or not), 2 refused (nothing was run).
"""
import argparse
import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from acceptance import intake  # noqa: E402

DIFF_PATH = re.compile(r"^diff --git a/(\S+) b/(\S+)$", re.M)


class Refused(Exception):
    pass


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def touched(patch_text):
    """The paths a patch touches (both sides of each diff header), in order, without duplicates."""
    return list(dict.fromkeys(p for pair in DIFF_PATH.findall(patch_text) for p in pair))


def base_files(repo, commit):
    """{path: (mode, blob sha)} of the commit's tree."""
    return {p: (m, s) for m, k, s, p in intake.tree_entries(repo, commit) if k == "blob"}


def apply(tree, patch):
    intake.git(tree, "apply", "--allow-empty", "--whitespace=nowarn", str(patch))


def restore(repo, commit, tree, paths):
    """Each path back to its content and mode at the commit, or removed if the commit does not have it."""
    files = base_files(repo, commit)
    for p in paths:
        target = Path(tree) / p
        if p in files:
            mode, sha = files[p]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(intake.git(repo, "cat-file", "blob", sha))
            target.chmod(0o755 if mode == "100755" else 0o644)
        elif target.exists():
            target.unlink()


def map_names(names, tree, test_files):
    """{name: node or None}: a name found as a test function in exactly one of test_files is `file::name`; a name
    that already is a node is kept if its file is one of them; anything else is None (missing)."""
    out = {}
    for name in names:
        if "::" in name:
            out[name] = name if name.split("::", 1)[0] in test_files else None
            continue
        hits = [f for f in test_files if (Path(tree) / f).exists()
                and re.search(rf"^\s*def {re.escape(name)}\s*\(", (Path(tree) / f).read_text(encoding="utf-8"), re.M)]
        out[name] = f"{hits[0]}::{name}" if len(hits) == 1 else None
    return out


def run_tests(tree, files, nodes, environment, sandbox_cfg, validate):
    spec = {"id": "swe", "executable": "python", "args": ["-m", "pytest", *files], "timeout_s": 600, "min_tests": 1,
            "max_skipped": 100000, "must_pass": sorted(set(nodes)), "environment": environment}
    return validate(spec, str(tree), sandbox_cfg)


def per_node(mapping, verdict):
    got = (verdict.get("evidence") or {}).get("must_pass") or {}
    return {name: ("missing" if node is None else "pass" if got.get(node) == "ok" else "fail")
            for name, node in mapping.items()}


def grade(*, instance, repo, review, sha, environment, sandbox_cfg, validate):
    inst, review = Path(instance), Path(review)
    patch = review / "changes.patch"
    prov = json.loads((review / "provenance.json").read_text(encoding="utf-8"))
    got = sha256(patch)
    if got != sha or got != (prov.get("patch") or {}).get("sha256"):
        raise Refused(f"changes.patch is {got}; --sha is {sha}, provenance.json says "
                      f"{(prov.get('patch') or {}).get('sha256')}: grade only the patch that was reviewed")
    base = (inst / "base_commit.txt").read_text().strip()
    test_patch = inst / "test_patch.diff"
    f2p = json.loads((inst / "FAIL_TO_PASS.txt").read_text())
    p2p = json.loads((inst / "PASS_TO_PASS.txt").read_text())
    tfiles = [p for p in touched(test_patch.read_text(encoding="utf-8")) if p.endswith(".py")]
    approved = [f["path"] for f in (prov.get("patch") or {}).get("files") or [] if f.get("approved_test")
                and f.get("change") != "D"]
    with tempfile.TemporaryDirectory() as tmp:
        tree = Path(tmp) / "graded"
        tree.mkdir()
        intake.write_tree(repo, base, tree, [])
        apply(tree, patch)
        approved_tests = {p: (tree / p).read_bytes() for p in approved if (tree / p).exists()}
        restore(repo, base, tree, touched(test_patch.read_text(encoding="utf-8")))
        apply(tree, test_patch)
        m2f, m2p = map_names(f2p, tree, tfiles), map_names(p2p, tree, tfiles)
        nodes = [n for n in list(m2f.values()) + list(m2p.values()) if n]
        v = run_tests(tree, tfiles, nodes, environment, sandbox_cfg, validate) if nodes else {}
        res_f2p, res_p2p = per_node(m2f, v), per_node(m2p, v)
        # information only: the approved tests on base_commit plus the maintainers' fix
        info = None
        if approved_tests:
            ref = Path(tmp) / "reference"
            ref.mkdir()
            intake.write_tree(repo, base, ref, [])
            apply(ref, inst / "patch.diff")
            for p, body in approved_tests.items():
                (ref / p).parent.mkdir(parents=True, exist_ok=True)
                (ref / p).write_bytes(body)
            spec = {"id": "drafter_tests", "executable": "python", "args": ["-m", "pytest", *approved_tests],
                    "timeout_s": 600, "min_tests": 1, "max_skipped": 100000, "must_pass": [],
                    "environment": environment}
            r = validate(spec, str(ref), sandbox_cfg)
            ev = r.get("evidence") or {}
            info = {"files": sorted(approved_tests), "status": r.get("status"), "tests_run": ev.get("tests_run"),
                    "failures": ev.get("failures"), "errors": ev.get("errors")}
    resolved = all(x == "pass" for x in res_f2p.values()) and all(x == "pass" for x in res_p2p.values())
    from tools import sandbox as sb
    return {"resolved": resolved, "FAIL_TO_PASS": res_f2p, "PASS_TO_PASS": res_p2p,
            "patch_sha256": got, "test_patch_sha256": sha256(test_patch), "base_commit": base,
            "environment": environment, "image": sb.environment_image(sandbox_cfg, environment)[0],
            "test_files": tfiles, "run": {k: (v.get("evidence") or {}).get(k) for k in
                                          ("tests_run", "failures", "errors", "skipped", "exit_code")} if v else None,
            "drafter_tests_on_reference": info,
            "note": "graded SWE-bench style by Argus (not the official harness); not comparable to leaderboards"}


def main(argv=None, validate=None, sandbox=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    for a in ("--instance", "--repo", "--review", "--sha", "--environment", "--out"):
        ap.add_argument(a, required=True)
    o = ap.parse_args(argv)
    if validate is None:
        from acceptance.validation import run_validation as validate
    if sandbox is None:
        sys.path.insert(0, str(ROOT / "scripts"))
        from approve_draft import sandbox_cfg
        sandbox = sandbox_cfg()
    try:
        out = grade(instance=o.instance, repo=o.repo, review=o.review, sha=o.sha, environment=o.environment,
                    sandbox_cfg=sandbox, validate=validate)
    except (Refused, intake.IntakeError, OSError, ValueError) as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    Path(o.out).write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"resolved: {out['resolved']}")
    for k in ("FAIL_TO_PASS", "PASS_TO_PASS"):
        bad = {n: s for n, s in out[k].items() if s != "pass"}
        print(f"{k}: {len(out[k]) - len(bad)}/{len(out[k])} pass" + (f"; not passing: {bad}" if bad else ""))
    if out["drafter_tests_on_reference"]:
        print(f"approved tests on the maintainers' fix: {out['drafter_tests_on_reference']['status']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
