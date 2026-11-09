"""Mutants for scripts/verify_at.sh and the verdict line of scripts/verify.sh: each broken alone; killed = a test
failed. Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
A, V = "scripts/verify_at.sh", "scripts/verify.sh"
T = ["tests/test_verify_at.py"]
M = [
    ("verify.sh: any PASS line", V, "grep '^RESULT: ' \"$LOG\" | tail -n 1 | grep -q '^RESULT: PASS'", "grep -q '^RESULT: PASS' \"$LOG\""),
    ("verify_at: any PASS line", A, "grep '^RESULT: ' \"$log\" | tail -n 1 | grep -q '^RESULT: PASS'", "grep -q '^RESULT: PASS' \"$log\""),
    ("no pins", A, '  cp -p "${pins[@]}" "$wt"/\n', "  true\n"),
    ("in the main checkout", A, '(cd "$wt" && bash scripts/verify.sh)', '(cd "$root" && bash scripts/verify.sh)'),
    ("no cleanup", A, "trap cleanup EXIT\n", ""),
    ("evidence not copied", A, 'cp -p "$log" "$root/verification/"\n', ""),
    ("no log passes", A, '  echo "verify_at: verify.sh wrote no log" >&2\n  exit 1', '  echo "verify_at: verify.sh wrote no log" >&2\n  exit 0'),
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
                               capture_output=True, text=True, timeout=600)
        finally:
            p.write_text(orig)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        k = r.returncode == 1 and "failed" in last          # a test failed (not a collection or internal error)
        killed += k
        print(f"{'KILLED ' if k else 'SURVIVED'} {name}: {last}", flush=True)
    print(f"RESULT: {killed}/{len(M)} killed")
