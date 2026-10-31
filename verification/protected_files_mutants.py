"""Mutants for SPEC_PROTECTED_FILES (the repository's .argus/protected, enforced by the harness): each applied alone in
a worktree, the named tests run with -x; killed = a test failed (an error or a skip is not a kill; a run with a skip is
reported as SKIPPED). Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
I, D, R, T_, V, J, C, DR = ("acceptance/intake.py", "acceptance/draft.py", "codetask/run.py", "codetask/tools.py",
                            "codetask/review.py", "router/job.py", "config.yaml", "codetask/drafter.py")
T = ["-rs", "tests/test_protected_files.py"]
M = [
    # 1. from the commit, never the working tree
    ("list read from the working tree", I, 'return parse_protected(git(repo, "cat-file", "blob", sha))',
     "return parse_protected((Path(repo) / PROTECTED_FILE).read_bytes())", T),
    # 6. a list that is not one
    ("bad glob accepted", I, "if not check_glob(line) or any(c.isspace() for c in line):", "if False:", T),
    ("no size limit", I, "    if len(globs) > MAX_PROTECTED:", "    if False:", T),
    ("a link is read as the list", I, 'if kind != "blob" or mode not in ("100644", "100755"):', 'if kind != "blob":', T),
    ("broken list leaves a job", J, '            raise Refused(f"{e}; no job was created") from e', "            protected = None",
     T),
    # 7. the list protects itself
    ("list does not protect itself", I, "    if PROTECTED_FILE not in globs:\n        globs.append(PROTECTED_FILE)",
     "    if False:\n        globs.append(PROTECTED_FILE)", T),
    # 2. frozen in the records
    ("intake record without the list", I, '"protected": read_protected(repo, full),', '"protected": None,', T),
    ("task record without the list", D, '"protected": base.get("protected"), "contract_sha256"',
     '"protected": None, "contract_sha256"', T),
    ("run setup does not freeze it", R, 'repo_protected = list(((record or {}).get("protected") or {}).get("globs") or [])',
     "repo_protected = []", T),
    # 3, 10. the draft check
    ("draft check ignores the list", D, '    globs = (protected or {}).get("globs") or []\n    if not globs:\n        return []',
     "    globs = []\n    if not globs:\n        return []", T),
    ("changed tests may change listed files", D, 'for t in draft.get("changed_tests") or [] if ct.matches(t["path"], globs)]',
     'for t in draft.get("changed_tests") or [] if False]', T),
    ("drafter not told", DR, "          if policy.get(\"repo_protected\") else []),", "          if False else []),", T),
    # 4, 8. the tools
    ("tools ignore the list", T_, "        if matches(norm, self.repo_protected):", "        if False:", T),
    # 5. the review package
    ("review ignores the list", V, 'elif matches(p, ((record or {}).get("protected") or {}).get("globs") or []):',
     "elif False:", T),
    # 9. an environment that requires the list
    ("required list not required", J, 'if protected is None and env_cfg.get("protected_required"):', "if False:", T),
    ("pwa_node22 does not require it", C, "      protected_required: true   #", "      protected_required: false  #", T),
    # P7: screens and status
    ("status does not name the list", J, '    if "protected_repo" in job.data:', "    if False:", T),
]
# Not listed (equivalent in the tests): the intake taking `commit` instead of the commit resolved before (`full`); the
# two differ only when the branch moves between the two git calls of one `argus code`.

if __name__ == "__main__":
    killed = 0
    for name, f, old, new, tests in M:
        p = WT / f
        orig = p.read_text()
        assert orig.count(old) == 1, (name, orig.count(old))
        p.write_text(orig.replace(old, new, 1))
        try:
            r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *tests], cwd=WT,
                               capture_output=True, text=True, timeout=1800)
        finally:
            p.write_text(orig)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        k = "failed" in last
        killed += k
        fails = [line for line in r.stdout.splitlines() if line.startswith("FAILED")][:1]
        verdict = "KILLED " if k else "SKIPPED" if "skipped" in last else "SURVIVED"
        print(f"{verdict} {name}: {fails or last}", flush=True)
    print(f"RESULT: {killed}/{len(M)} killed")
