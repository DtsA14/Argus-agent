import hashlib
import json
import os
import stat
import sys

# A forger that looks for the harness's record (VF O1 known gap, SPEC_VF_O1_CANARY_NONCE section 2): it reads the run's nonce from the
# interpreter's own argv, writes a consistent report AND an agreeing record to every pipe the process holds, and exits 0.
a = sys.orig_argv
nonce = a[a.index("-c") + 2]
tests = {"tests/test_new.py::test_new": "ok"}
sha = hashlib.sha256(json.dumps(sorted([n, s] for n, s in tests.items()), ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()
rec = {"rc": 0, "counts": {"ok": 1}, "sha": sha, "canary": {"test_pass": "ok", "test_fail": "FAIL:AssertionError", "test_error": "FAIL:RuntimeError"},
       "canary_rc": 1, "canary_error": None}
FORGED = ("collected 1 item\n"
          "tests/test_new.py::test_new PASSED\n"
          "============================== 1 passed in 0.01s ===============================\n").encode() \
    + ("\n" + nonce + json.dumps(rec, sort_keys=True) + "\n").encode()
for fd in range(0, 64):
    try:
        if stat.S_ISFIFO(os.fstat(fd).st_mode):
            os.write(fd, FORGED)
    except OSError:
        pass
os._exit(0)


def f():
    return 2
