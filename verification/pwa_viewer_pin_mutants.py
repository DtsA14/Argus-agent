"""Mutants for the SW_SHA256 pin (SPEC_PWA_VIEWER §10.1, A3): each applied alone in a worktree, the pin tests run with
-x; killed = a test failed (an error or a skip is not a kill; a run with a skip is reported as SKIPPED, the Docker tests
must run). Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
V = "router/stage_viewer.py"
PIN = 'SW_SHA256 = "db58777a410480de1dac10c17f730396dcaee0031ea693dbd03e2db418c7e0cf"'
F = "tests/test_stage_viewer.py::"
T = [F + n for n in ("test_the_pinned_service_worker_is_the_reviewed_one_of_the_fixture",
                     "test_the_default_pin_refuses_a_service_worker_that_differs_by_one_byte",
                     "test_a_real_deploy_with_the_default_pin_publishes_the_reviewed_service_worker",
                     "test_a_real_deploy_with_another_service_worker_is_refused_by_the_default_pin",
                     "test_only_the_reviewed_sw_js_is_served_as_a_service_worker_script",
                     "test_a_dist_that_breaks_a_rule_is_refused")]
M = [
    ("pin removed", V, PIN, "SW_SHA256 = None", T),
    ("another pin", V, PIN, 'SW_SHA256 = "' + "0" * 64 + '"', T),
    ("default is not the pin", V, "def __init__(self, base=None, ledger=None, sw_sha256=SW_SHA256):",
     "def __init__(self, base=None, ledger=None, sw_sha256=None):", T),
    ("pin not checked", V, 'if path == "sw.js" and hashlib.sha256(data).hexdigest() != sw_sha256:',
     'if False and path == "sw.js":', T),
    ("unpinned accepts anything", V, 'if path == "sw.js" and hashlib.sha256(data).hexdigest() != sw_sha256:',
     'if path == "sw.js" and sw_sha256 is None:', T),
    # security review: a second service worker at root scope
    ("any script served as a service worker", V, 'if "Service-Worker" in self.headers and path.split', 'if False and path.split', T),
    ("top-level script allowed", V, 'if ext == ".js" and "/" not in path and path != "sw.js":', "if False:", T),
]

if __name__ == "__main__":
    killed = 0
    for name, f, old, new, tests in M:
        p = WT / f
        orig = p.read_text()
        assert orig.count(old) == 1, (name, orig.count(old))
        p.write_text(orig.replace(old, new, 1))
        try:
            r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-rs", "-p", "no:cacheprovider", *tests], cwd=WT,
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
# Not listed: dropping the query string before comparing with /sw.js (stricter, not weaker: /sw.js?x would be refused).
