"""Mutants for SPEC_VITEST_FULL_REGRESSION amendment 1 (F5: the harness's old_tests_* validations): each guarantee broken
alone; killed = a test failed. Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
D = "codetask/drafter.py"
A = "acceptance/draft.py"
T = ["tests/test_vitest_full_regression.py", "tests/test_drafter.py", "tests/test_draft.py"]
M = [
    ("no old_tests", D, "        specs += old_tests_validations(specs, base_files, policy)", "        pass"),
    ("python drafts get them", D, "    if vitest and base_files is not None:", "    if base_files is not None:"),
    ("no cut at 15", D, 'OLD_TESTS_ID, OLD_TESTS_PER = "old_tests_{}", 15', 'OLD_TESTS_ID, OLD_TESTS_PER = "old_tests_{}", 100'),
    ("ids collide", D, "        while OLD_TESTS_ID.format(n) in used:\n            n += 1\n", ""),
    ("min_tests one", D, '"min_tests": len(files), "max_skipped": 0,', '"min_tests": 1, "max_skipped": 0,'),
    ("old must_pass kept empty broken", D, '"must_pass": [], "environment": policy["environment"]})\n        used.add',
     '"must_pass": files, "environment": policy["environment"]})\n        used.add'),
    ("named counted unnamed", D, "    named = {p for v in specs for p in v[\"args\"][1:]}", "    named = set()"),
    ("bad id crashes", D, '{v["id"] for v in specs if isinstance(v["id"], str)}', '{v["id"] for v in specs}'),
    ("intake files not given", D, "                                          base_files=snapshot(intake_dir, skip_cache=True)",
     "                                          base_files=snapshot(intake_dir, skip_cache=False)"),
    ("excluded dirs taken", A, "            and not VITEST_EXCLUDED_DIRS.intersection(f.split(\"/\")[:-1]) and VITEST_FILE",
     "            and VITEST_FILE"),
    ("unplain taken", A, "VITEST_FILE.match(f) and intake._plain(f)]", "VITEST_FILE.match(f)]"),
    ("version kept", D, '"SubmitDraft": f"4:{tool_version(scfg, [env])}"', '"SubmitDraft": f"3:{tool_version(scfg, [env])}"'),
    ("prompt still asks for every file", D, '"- Name validations only for the new tests and the existing test files close to the change. Every other existing "',
     '"- Name every existing test file (*.test.*) in a validation. Every other existing "'),
]

if __name__ == "__main__":
    killed = 0
    for name, f, old, new in M:
        p = WT / f
        orig = p.read_text()
        assert orig.count(old) == 1, (name, orig.count(old))
        p.write_text(orig.replace(old, new, 1))
        try:
            r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *T], cwd=WT,
                               capture_output=True, text=True, timeout=900)
        finally:
            p.write_text(orig)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        k = r.returncode == 1 and "failed" in last          # a test failed (not a collection or internal error)
        killed += k
        print(f"{'KILLED ' if k else 'SURVIVED'} {name}: {last}", flush=True)
    print(f"RESULT: {killed}/{len(M)} killed")
