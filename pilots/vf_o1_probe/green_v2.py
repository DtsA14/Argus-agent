"""Pilot GREEN script (SPEC_VF_O1_CANARY_NONCE rev 2, section 3). Run as: python3 -I -B -c <this file's text> NONCE TARGET...
Session 1: the contract's tests, text as today, plus a recorder. Session 2: three canary tests of the harness. Then one record line."""
import contextlib, hashlib, io, json, os, sys, tempfile
nonce, targets = sys.argv[1], sys.argv[2:]
import pytest
import pytest.__main__ as _pm
sys.argv = [_pm.__file__, *targets]
FIXED = ["-p", "no:cacheprovider", "-o", "addopts=", "-o", "console_output_style=classic",
         "--rootdir", "/workspace", "-v", "--tb=short", "--color=no", "-rN"]
WORD = {"PASSED": "ok", "FAILED": "FAIL", "ERROR": "ERROR", "SKIPPED": "skipped", "XFAIL": "expected failure", "XPASS": "unexpected success"}
RANK = {"ERROR": 2, "FAIL": 1}


class Rec:
    def __init__(self):
        self.tests, self.exc, self.cfg = {}, {}, None

    def pytest_configure(self, config):
        self.cfg = config

    def pytest_runtest_makereport(self, item, call):
        if call.excinfo is not None:
            self.exc[item.nodeid] = call.excinfo.type.__name__

    def pytest_runtest_logreport(self, report):
        if hasattr(report, "context"):                       # a subtest report: not a line of the text (spec, item 5)
            return
        word = self.cfg.hook.pytest_report_teststatus(report=report, config=self.cfg)[2]
        word = word[0] if isinstance(word, tuple) else word
        status = WORD.get(word)
        if status is None:
            return
        old = self.tests.get(report.nodeid)
        if old is None or RANK.get(status, 0) > RANK.get(old, 0):    # first report wins among ties, as parse_pytest
            self.tests[report.nodeid] = status


def sha(tests):
    pairs = sorted([n, s] for n, s in tests.items())
    return hashlib.sha256(json.dumps(pairs, ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()


r1 = Rec()
rc1 = int(pytest.main([*FIXED, *targets], plugins=[r1]))
canary, rc2, err = {}, None, None
for k in ("PYTEST_ADDOPTS", "PYTEST_PLUGINS"):
    os.environ.pop(k, None)
try:
    tag = os.urandom(8).hex()
    d = tempfile.mkdtemp(prefix="argus_canary_", dir="/tmp")
    with open(f"{d}/pytest.ini", "w") as f:
        f.write("[pytest]\n")
    p = f"{d}/test_argus_canary_{tag}.py"
    with open(p, "w") as f:
        f.write(f"def test_pass_{tag}(): assert 1 == 1\ndef test_fail_{tag}(): assert 1 == 2\ndef test_error_{tag}(): raise RuntimeError('x')\n")
    r2 = Rec()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        rc2 = int(pytest.main(["-c", f"{d}/pytest.ini", "--confcutdir", d, "--rootdir", d, "-p", "no:cacheprovider",
                               "-o", "addopts=", "-q", "--tb=no", "--color=no", p], plugins=[r2]))
    for n, s in r2.tests.items():
        short = n.split("::")[-1].rsplit("_", 1)[0]
        canary[short] = s if s == "ok" else f"{s}:{r2.exc.get(n)}"
except OSError as e:
    err = type(e).__name__
rec = {"rc": rc1, "counts": {s: sum(1 for v in r1.tests.values() if v == s) for s in sorted(set(r1.tests.values()))},
       "sha": sha(r1.tests), "canary": canary, "canary_rc": rc2, "canary_error": err}
sys.stdout.write("\n" + nonce + json.dumps(rec, sort_keys=True) + "\n")
sys.stdout.flush()
sys.exit(rc1)
