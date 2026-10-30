"""Mutants for the monitor failure notification (router/stage_alert.py, its CLI wiring): each alone; killed = a test
failed. Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
A, C, T = "router/stage_alert.py", "scripts/argus.py", ["tests/test_stage_alert.py"]
M = [
    ("threshold 2", A, "FAILS_IN_A_ROW = 3", "FAILS_IN_A_ROW = 2", T),
    ("busy counted as failure", A, 'decided = [r for r in records if isinstance(r.get("ok"), bool)]',
     "decided = [{**r, 'ok': bool(r.get('ok'))} for r in records]", T),
    ("stuck never reported", A, "        elif busy >= BUSY_IN_A_ROW and not state[\"alerted\"]:", "        elif False:", T),
    ("stuck after 3", A, "BUSY_IN_A_ROW = 4", "BUSY_IN_A_ROW = 3", T),
    ("alert every run", A, "        if failed >= FAILS_IN_A_ROW and not state[\"alerted\"]:",
     "        if failed >= FAILS_IN_A_ROW:", T),
    ("no recovery message", A, "        elif failed == 0 and busy == 0 and last is not None and state[\"alerted\"]:",
     "        elif False:", T),
    ("unsent recovery blocks the next FAIL", A, "                state.update(alerted=False, at=now, title=title)   # never",
     "                state.update(alerted=why is not None, at=now, title=title)   # never", T),
    ("unsent recovery dropped", A, '                    state["pending"] = {"title": title, "text": text}', "                    pass", T),
    ("unsent FAIL counted as sent", A, "                    state.update(unsent=why, unsent_at=now)",
     "                    state.update(alerted=True, unsent=why, unsent_at=now)", T),
    ("app answer sent", A, 'return f"answered {m.group(1)}" if m else str(detail)[:160]', "return str(detail)[:160]", T),
    ("refresh reason sent", A, '        lines.append(f"refresh failed ({kind[:40] or \'unknown\'})")',
     '        lines.append(f"refresh failed ({refresh.get(\'why\')})")', T),
    ("viewer left out", A, '        lines += _failed(viewer.get("smoke"))\n', "", T),
    ("viewer why left out", A, '            lines.append(str(viewer["why"])[:160])', "            pass", T),
    ("topic readable by others", A, "        if st.st_mode & 0o077:", "        if False:", T),
    ("topic through a link", A, "os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)", "os.O_RDONLY | os.O_NONBLOCK)", T),
    ("redirects followed", A, "build_opener(_NoRedirect)", "build_opener()", T),
    ("no lock", A, "        fcntl.flock(fd, fcntl.LOCK_EX)", "        pass", T),
    ("state readable by others", A, "os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)", "os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)", T),
    ("CLI without the alert", C, "                    print(json.dumps(rec, sort_keys=True))\n                    _alert(sa, st)\n",
     "                    print(json.dumps(rec, sort_keys=True))\n", T),
    ("CLI alert changes the exit code", C, "    except Exception as e:                               # noqa: BLE001\n        sent = f\"{type(e).__name__}: {e}\"",
     "    except OSError:\n        raise", T),
    ("crashed run not recorded", C, '''                        sd._append(st.base / "monitor.jsonl", {''',
     '''                        (lambda *a: None)(st.base / "monitor.jsonl", {''', T),
]
# Equivalent, not listed: the S_ISREG check of the topic file (O_NOFOLLOW refuses a link; a fifo or device opened with
# O_NONBLOCK reads no topic name).

if __name__ == "__main__":
    killed = 0
    for name, f, old, new, tests in M:
        p = WT / f
        orig = p.read_text()
        assert orig.count(old) == 1, (name, orig.count(old))
        p.write_text(orig.replace(old, new, 1))
        r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *tests], cwd=WT,
                           capture_output=True, text=True, timeout=120)
        p.write_text(orig)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        k = "failed" in last
        killed += k
        print(f"{'KILLED ' if k else 'SURVIVED'} {name}: {last}", flush=True)
    print(f"RESULT: {killed}/{len(M)} killed")
