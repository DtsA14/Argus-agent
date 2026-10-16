"""Check the pilot tests against variants of acceptance/validation.py: the current code, a reference fix, and two
wrong fixes. Run from the scratch pilot workspace: python pilot_variants.py <workspace>."""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

WS = Path(sys.argv[1])
SRC = (WS / "acceptance" / "validation.py").read_text(encoding="utf-8")

LOOP_OLD = '''        m = TEST_LINE.match(line)
        if m:'''
REF = '''        s = SUBTEST_LINE.match(line)
        if s:                                 # "  test_x (id) (params) ... FAIL": a subTest of an earlier test
            name, tid, status = s.groups()
            if tid.rsplit(".", 1)[-1] == name and status in ("FAIL", "ERROR"):
                if tests.get(tid) != "ERROR":
                    tests[tid] = status
            continue
        m = TEST_LINE.match(line)
        if m:'''
REF_RE = '''RAN = re.compile('''
REF_RE_NEW = '''SUBTEST_LINE = re.compile(r"^\\s+(\\w+) \\(([\\w.]+)\\) \\(.*\\) \\.\\.\\. (\\w+)$")
RAN = re.compile('''

VARIANTS = {
    "current": SRC,
    "reference": SRC.replace(LOOP_OLD, REF).replace(REF_RE, REF_RE_NEW, 1),
    # wrong 1: an empty status is read as passing
    "empty_is_ok": SRC.replace('tests[tid] = rest[4:].strip()', 'tests[tid] = rest[4:].strip() or "ok"'),
    # wrong 2: the first subTest status decides
    "first_wins": SRC.replace(LOOP_OLD, REF.replace('''                if tests.get(tid) != "ERROR":
                    tests[tid] = status''', '''                if tests.get(tid) in (None, ""):
                    tests[tid] = status''')).replace(REF_RE, REF_RE_NEW, 1),
}
for name, code in VARIANTS.items():
    assert name == "current" or code != SRC, name
    with tempfile.TemporaryDirectory() as t:
        ws = Path(t) / "ws"
        shutil.copytree(WS, ws)
        (ws / "acceptance" / "validation.py").write_text(code, encoding="utf-8")
        res = []
        for pat in ("test_subtest_status.py", "test_parser_regression.py"):
            r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "pilot_tests", "-t", ".", "-p", pat],
                               cwd=ws, capture_output=True, text=True)
            res.append(f"{pat.split('_')[1]}: {r.stderr.strip().splitlines()[-1]}")
        print(f"{name:<12}", " | ".join(res))
