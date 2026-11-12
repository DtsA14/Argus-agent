"""Mutants for SPEC_TEST_DETECTION_TERMINAL (GATE) and the two small RC fixes made with it (codetask/run.py, router/job.py,
codetask/tools.py, codetask/agent.py): each applied alone in a worktree; killed = a test failed (an error or a skip is not a kill).
Usage: test_detection_terminal_mutants.py <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
R, J, T, A = "codetask/run.py", "router/job.py", "codetask/tools.py", "codetask/agent.py"
TESTS = ["tests/test_detection_terminal.py", "tests/test_report_conflict.py"]
M = [
    ("gate: a hit is not terminal", R, "        if hit:\n            ev = hit.get", "        if False:\n            ev = hit.get"),
    ("gate: another criterion id", R, 'c["id"] == testdetect.ID and c["status"] == "fail"', 'c["id"] == "scope:other" and c["status"] == "fail"'),
    ("gate: a passing criterion counts", R, 'c["id"] == testdetect.ID and c["status"] == "fail"', 'c["id"] == testdetect.ID and c["status"] != "x"'),
    ("gate: another stop reason", R, 'reason="test_detection: production code', 'reason="stagnant: production code'),
    ("gate: the summary lacks the total", R, 'summary["detected"] = {"total": ev.get("total"),', 'summary["detected"] = {"total": None,'),
    ("gate: no limit of five hits", R, '(ev.get("hits") or [])[:5]]}', '(ev.get("hits") or [])]}'),
    ("gate: the text of the line is kept", R, 'for k in ("path", "line", "pattern")}', 'for k in ("path", "line", "pattern", "text")}'),
    ("gate: the conflict state is dropped", R, "failures=history, **new_conflict,\n                        reason=\"test_detection",
     "failures=history,\n                        reason=\"test_detection"),
    ("gate: the human is not shown the hits", J, "            out += detection_lines(job)\n", ""),
    ("gate: the extra hits are not counted", J, 'if isinstance(d.get("total"), int) and d["total"] > len(listed) else ""', 'if False else ""'),
    ("gate: no list of hits crashes the line", J, 'listed = d.get("hits") or []', 'listed = d["hits"]'),
    ("rc: a human-judged run is told it reported", T, 'if self.conflict.get("by_human"):', "if False:"),
    ("rc: the next prompt shows the raw token", A, 'end = {"conflict_reported": "with a report of a conflict that the harness did not confirm"}.get(s.get("end"), s.get("end"))',
     'end = s.get("end")'),
]

if __name__ == "__main__":
    killed = 0
    for name, f, old, new in M:
        p = WT / f
        orig = p.read_text()
        assert orig.count(old) == 1, (name, orig.count(old))
        p.write_text(orig.replace(old, new, 1))
        r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *TESTS], cwd=WT, capture_output=True, text=True)
        p.write_text(orig)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        k = "failed" in last
        killed += k
        fails = [line for line in r.stdout.splitlines() if line.startswith("FAILED")][:1]
        print(f"{'KILLED ' if k else 'SURVIVED'} {name}: {fails or last}", flush=True)
    print(f"RESULT: {killed}/{len(M)} killed")
