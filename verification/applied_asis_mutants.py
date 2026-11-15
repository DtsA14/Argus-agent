"""Mutants for SPEC_ARGUS_APPLY PR 1 (applied(): the comparison as the package makes the patch, clean git environment, patch sha in job.json, the
recorder without the lock): each applied alone in a worktree; killed = a test FAILED and pytest reported no error. Usage: <this> <worktree> <python>
Not listed: `-c diff.renames=false` (redundant with --no-renames, an equivalent mutant)."""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
T = ["-rfEs", "tests/test_applied_asis.py", "tests/test_router.py"]
J, I = "router/job.py", "acceptance/intake.py"
M = [
    ("intake.git(clean) keeps GIT_* variables", I, [("    base = {k: v for k, v in os.environ.items() if not k.startswith(\"GIT_\") and k != \"EMAIL\"} if clean else dict(os.environ)", "    base = dict(os.environ)")]),
    ("show without --binary", J, [("\"--no-textconv\", \"--binary\", \"--full-index\"", "\"--no-textconv\", \"--full-index\"")]),
    ("show without --full-index", J, [("\"--binary\", \"--full-index\", \"--no-renames\"", "\"--binary\", \"--no-renames\"")]),
    ("show without --no-renames", J, [("\"--full-index\", \"--no-renames\", \"--format=\")", "\"--full-index\", \"--format=\")")]),
    ("show without --no-textconv", J, [("\"--no-ext-diff\", \"--no-textconv\",", "\"--no-ext-diff\",")]),
    ("no diff.noprefix override", J, [("\"-c\", \"diff.noprefix=false\", ", "")]),
    ("no diff.mnemonicPrefix override", J, [("\"-c\", \"diff.mnemonicPrefix=false\", ", "")]),
    ("patch_id not clean", J, [("data=diff, clean=True).split()", "data=diff).split()")]),
    ("rev-parse not clean", J, [("f\"{commit}^{{commit}}\", clean=True).decode()", "f\"{commit}^{{commit}}\").decode()")]),
    ("show not clean", J, [("*SHOW_AS_PACKAGED, sha, clean=True)", "*SHOW_AS_PACKAGED, sha)")]),
    ("patch sha not recorded in job.json", J, [("\"dir\": str(out[\"dir\"]), \"patch_sha256\": patch_sha}", "\"dir\": str(out[\"dir\"]), \"patch_sha256\": None}")]),
    ("applied() without the lock", J, [("    with job.lock():\n        return _record_applied(job, commit, deps=deps, note=note)", "    return _record_applied(job, commit, deps=deps, note=note)")]),
    ("extra fields dropped from the log entry", J, [("**({\"note\": note} if note else {}), **extra)", "**({\"note\": note} if note else {}))")]),
    ("state not checked in the recorder", J, [("    if job.data[\"state\"] != REVIEW_READY:\n        raise Refused(f\"job {job.id} is {job.data['state']}: only a valid review package is applied\")\n    repo = job.data[\"inputs\"][\"repo\"]\n    patch = Path(last_agent(job)[1][\"review\"][\"dir\"]) / \"changes.patch\"\n    try:\n        sha = intake.git(repo, \"rev-parse\"", "    repo = job.data[\"inputs\"][\"repo\"]\n    patch = Path(last_agent(job)[1][\"review\"][\"dir\"]) / \"changes.patch\"\n    try:\n        sha = intake.git(repo, \"rev-parse\"")]),
    ("as_is always True", J, [("as_is=None if mine is None or theirs is None else mine == theirs, by=os.environ.get(\"USER\"),\n             **({\"note\"", "as_is=True, by=os.environ.get(\"USER\"),\n             **({\"note\"")]),
]

if __name__ == "__main__":
    killed = 0
    for name, F, edits in M:
        p = WT / F
        orig = p.read_text()
        text = orig
        stale = [a[:60] for a, _ in edits if text.count(a) != 1]
        if stale:
            print(f"STALE   {name}: {stale}", flush=True)
            continue
        for a, b in edits:
            text = text.replace(a, b, 1)
        p.write_text(text)
        try:
            r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *T], cwd=WT, capture_output=True, text=True, timeout=1800)
        finally:
            p.write_text(orig)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        fails = [line for line in r.stdout.splitlines() if line.startswith("FAILED tests/test_")][:1]
        k = bool(fails) and "error" not in last
        killed += k
        print(f"{'KILLED ' if k else 'ERROR  ' if 'error' in last else 'SURVIVED'} {name}: {fails or last}", flush=True)
    print(f"RESULT: {killed}/{len(M)} killed")
