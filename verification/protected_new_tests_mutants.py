"""Mutants for the apply/card rule on new approved tests that match .argus/protected (SPEC_PROTECTED_FILES 10). Applied alone; killed = a test FAILED.
Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
PF, AP, AC, RV = "router/protected_files.py", "router/apply.py", "router/approve_code.py", "codetask/review.py"
T = ["-rfEs", "tests/test_apply_cmd.py", "tests/test_approve_code.py", "tests/test_review.py"]
# Result 2026-11-21: 16/18 killed; the two survivors are equivalent: "anything ending _test.py anywhere" (`.*_test\.py` and `[^/]*_test\.py` match the same paths
# once the leading (^|/) and the end anchor hold) and "apply accepts any old mode" (a file git reports as status A always has old mode 000000).
M = [
    ("a modified file passes as new", PF, [('f.get("change") == "A"', 'f.get("change") in ("A", "M")')]),
    ("a truthy approved_test passes", PF, [('f.get("approved_test") is True', 'bool(f.get("approved_test"))')]),
    ("any new approved file passes, test name or not", PF, [(' and bool(TEST_NAME.search(p))', '')]),
    ("a name may contain test_ in the middle", PF, [('r"(^|/)(test_[^/]*\\.py', 'r"(test_[^/]*\\.py')]),
    ("the name is not anchored at the end", PF, [('tsx))$")', 'tsx))")')]),
    ("any extension passes as a vitest test", PF, [('(js|jsx|ts|tsx)', '[a-z]+')]),
    ("anything ending _test.py anywhere", PF, [('[^/]*_test\\.py', '.*_test\\.py')]),
    ("an unreadable glob does not protect", PF, [('        return True                                          # a glob that cannot be read protects', '        return False')]),
    ("stopped ignores the new-test exception being absent", PF, [('and not is_new_approved_test(f)]\n\n\ndef allowed_new_tests', 'and True]\n\n\ndef allowed_new_tests')]),
    ("stopped does not look at the globs", PF, [('and match_of(f["path"], globs) and not is_new_approved_test(f)]', 'and not is_new_approved_test(f)]')]),
    ("apply does not check the protected list", AP, [('    hit = protected_files.stopped(pfiles, globs)', '    hit = []')]),
    ("apply does not compare git's status", AP, [('        if status != "A" or old != "000000":', '        if False:')]),
    ("apply accepts any old mode", AP, [('        if status != "A" or old != "000000":', '        if status != "A":')]),
    ("apply accepts a deletion as new", AP, [('        if status != "A" or old != "000000":', '        if status == "M":')]),
    ("the card uses the old matcher for (c)", AC, [('protected = protected_files.stopped(pfiles, globs) ', 'protected = [p for p in listed if self._protected(p, globs)] ')]),
    ("the card never shows the new-test mark", AC, [('            if p in new_tests:\n                marks.append(NEW_TEST_MARK)', '            if False:\n                marks.append(NEW_TEST_MARK)')]),
    ("the card allows every protected file", AC, [('new_tests = set(protected_files.allowed_new_tests(pfiles, globs))', 'new_tests = set(listed)')]),
    ("review lists modified files as added", RV, [('("A", from_base["added"])', '("A", from_base["added"] + from_base["modified"])')]),
]
killed = 0
for name, f, edits in M:
    p = WT / f
    orig = p.read_text()
    text = orig
    if any(text.count(a) != 1 for a, _ in edits):
        print("STALE  ", name, flush=True)
        continue
    for a, b in edits:
        text = text.replace(a, b, 1)
    p.write_text(text)
    try:
        r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", "-n", "4", *T], cwd=WT, capture_output=True, text=True, timeout=900)
    finally:
        p.write_text(orig)
    last = (r.stdout.strip().splitlines() or [""])[-1]
    k = "FAILED tests/" in r.stdout or "FAILED" in last
    killed += k
    print("KILLED " if k else "SURVIVED", name, flush=True)
print(f"RESULT: {killed}/{len(M)} killed")
