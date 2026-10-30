"""Mutants for the SW_SHA256 pin (SPEC_PWA_VIEWER §10.1, A3): each applied alone in a worktree, the pin tests run with
-x; killed = a test failed (an error or a skip is not a kill). Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
V = "router/stage_viewer.py"
PIN = 'SW_SHA256 = "db58777a410480de1dac10c17f730396dcaee0031ea693dbd03e2db418c7e0cf"'
T = ["tests/test_stage_viewer.py", "-k", "pin"]
M = [
    ("pin removed", V, PIN, "SW_SHA256 = None", T),
    ("another pin", V, PIN, 'SW_SHA256 = "' + "0" * 64 + '"', T),
    ("default is not the pin", V, "def __init__(self, base=None, ledger=None, sw_sha256=SW_SHA256):",
     "def __init__(self, base=None, ledger=None, sw_sha256=None):", T),
    ("pin not checked", V, 'if path == "sw.js" and hashlib.sha256(data).hexdigest() != sw_sha256:',
     'if False and path == "sw.js":', T),
    ("unpinned accepts anything", V, 'if path == "sw.js" and hashlib.sha256(data).hexdigest() != sw_sha256:',
     'if path == "sw.js" and sw_sha256 is None:', T),
]

if __name__ == "__main__":
    killed = 0
    for name, f, old, new, tests in M:
        p = WT / f
        orig = p.read_text()
        assert orig.count(old) == 1, (name, orig.count(old))
        p.write_text(orig.replace(old, new, 1))
        r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *tests], cwd=WT,
                           capture_output=True, text=True)
        p.write_text(orig)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        k = "failed" in last
        killed += k
        fails = [line for line in r.stdout.splitlines() if line.startswith("FAILED")][:1]
        print(f"{'KILLED ' if k else 'SURVIVED'} {name}: {fails or last}", flush=True)
    print(f"RESULT: {killed}/{len(M)} killed")
