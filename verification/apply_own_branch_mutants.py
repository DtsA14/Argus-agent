"""Mutants for `argus apply` making its own branch when the repository is on its main line (SPEC_ARGUS_APPLY K3, revision 2026-11-22). Applied alone; killed = a test FAILED.
Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
AP = "router/apply.py"
T = ["-rfEs", "tests/test_apply_cmd.py"]
# Result 2026-11-22: 17/17 killed (the one survivor of the first run, the two refusal texts swapped, closed by a test naming the text).
M = [
    ("master is not a main line", [('("main", "master")', '("main",)')]),
    ("origin/HEAD is not looked at", [('    return out == f"refs/remotes/origin/{branch}"', '    return False')]),
    ("origin/HEAD compares the wrong ref", [('    return out == f"refs/remotes/origin/{branch}"', '    return out == f"refs/remotes/{branch}"')]),
    ("no origin/HEAD is an error", [('"refs/remotes/origin/HEAD", ok=(0, 1)', '"refs/remotes/origin/HEAD", ok=(0,)')]),
    ("the own branch is made on every branch", [('    if _is_main_line(repo, first_branch):', '    if True:')]),
    ("the own branch is never made", [('    if _is_main_line(repo, first_branch):', '    if False:')]),
    ("an existing own branch is not looked at", [('            if there:\n', '            if False:\n')]),
    ("a branch at another commit is called the base", [('if there != head else', 'if True else')]),
    ("the branch is made but not checked out", [('run_git(repo, "checkout", "-q", "-b", own_branch)', 'run_git(repo, "branch", own_branch)')]),
    ("the record keeps the first branch", [('        ref = f"refs/heads/{own_branch}"\n', '')]),
    ("a failed commit does not leave the own branch", [('    back = bool(own_branch) and undone and _leave_own_branch(repo, first_branch, own_branch)', '    back = True')]),
    ("the rollback goes back to the own branch", [('run_git(repo, "checkout", "-q", first)', 'run_git(repo, "checkout", "-q", own)')]),
    ("the rollback keeps the own branch", [('        run_git(repo, "branch", "-q", "-D", own)\n', '')]),
    ("rollback despite a failed undo", [('bool(own_branch) and undone and _leave', 'bool(own_branch) and _leave')]),
    ("a failed rollback says nothing", [('if own_branch and not back else ""', 'if False else ""')]),
    ("a failed log write leaves the own branch", [('        if own_branch:\n            _leave_own_branch(repo, first_branch, own_branch)\n        raise', '        raise')]),
    ("git trouble making the branch is a traceback", [('        except (GitFail, subprocess.TimeoutExpired) as e:           # nothing was changed yet', '        except ZeroDivisionError as e:           # nothing was changed yet')]),
]
killed = 0
for name, edits in M:
    p = WT / AP
    orig = p.read_text()
    text = orig
    if any(text.count(a) != 1 for a, _ in edits):
        print("STALE  ", name, flush=True)
        continue
    for a, b in edits:
        text = text.replace(a, b, 1)
    p.write_text(text)
    try:
        r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *T, "-k", "branch or main_line or kill or own or undo or argus or holds or pointed or crash"],
                           cwd=WT, capture_output=True, text=True, timeout=900)
    finally:
        p.write_text(orig)
    k = "FAILED tests/" in r.stdout
    killed += k
    print("KILLED " if k else "SURVIVED", name, flush=True)
print(f"RESULT: {killed}/{len(M)} killed")
