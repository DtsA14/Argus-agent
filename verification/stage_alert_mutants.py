"""Mutants for the monitor failure notification (router/stage_alert.py): each alone; killed = a test failed.
Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
A, T = "router/stage_alert.py", ["tests/test_stage_alert.py"]
M = [
    ("threshold 2", A, "FAILS_IN_A_ROW = 3", "FAILS_IN_A_ROW = 2", T),
    ("busy counted as failure", A, 'decided = [r for r in records if isinstance(r.get("ok"), bool)]',
     "decided = [{**r, 'ok': bool(r.get('ok'))} for r in records]", T),
    ("busy breaks the run", A, 'decided = [r for r in records if isinstance(r.get("ok"), bool)]',
     "decided = [r for r in records if r.get('ok') is not None or r.update(ok=True) or True]", T),
    ("alert every run", A, "if n >= FAILS_IN_A_ROW and not state[\"alerted\"]:", "if n >= FAILS_IN_A_ROW:", T),
    ("no recovery message", A, 'elif n == 0 and state["alerted"]:', "elif False:", T),
    ("app answer sent", A, 'return f"answered {m.group(1)}" if m else str(detail)[:160]', "return str(detail)[:160]", T),
    ("refresh reason sent", A, '        lines.append(f"refresh failed ({kind[:40] or \'unknown\'})")',
     '        lines.append(f"refresh failed ({refresh.get(\'why\')})")', T),
    ("viewer left out", A, '        lines += _failed(viewer.get("smoke"))', "        pass", T),
    ("topic readable by others", A, "    if st.st_mode & 0o077:", "    if False:", T),
    ("unsent counted as sent", A, '        _save(base, {**state, "unsent"', '        _save(base, {**state, "alerted": True, "unsent"', T),
    ("state readable by others", A, "os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)", "os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)", T),
]
# Equivalent, not listed: the S_ISLNK check of the topic file (lstat gives a link mode 0777, which the 0o077 check
# refuses already).

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
        print(f"{'KILLED ' if k else 'SURVIVED'} {name}: {last}", flush=True)
    print(f"RESULT: {killed}/{len(M)} killed")
