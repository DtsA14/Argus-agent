"""Mutants for SPEC_BUDGET_V2 part 1 (rev 1 section D). Applied alone; killed = a test FAILED. Run in a throwaway worktree.
Usage: <this> <worktree> <python> [name-part ...]"""
import os
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
ONLY = sys.argv[3:]
B, JS, C = "router/budget.py", "router/chat_static/app.js", "router/chat.py"
T = ["tests/test_budget.py", "tests/test_chat_budget.py", "tests/test_chat_ui.py", "tests/test_chat.py"]
M = [
    ("a started call without its end counts nothing", B, [("                calls += [s for c, s in f.started.items() if c not in f.final]", "                calls += []")]),
    ("a started call is counted again beside its end", B, [("                calls += [s for c, s in f.started.items() if c not in f.final]", "                calls += list(f.started.values())")]),
    ("a refused call is summed", B, [('e.get("status") != "refused":', "True:")]),
    ("the patch reader ledger is left out", B, [('                out.append((os.path.join(p, "patch_read_ledger.jsonl"), n))', "                pass")]),
    ("a fixture ledger inside a snapshot is read", B, [('                    out.append((os.path.join(p, "runs", r, "events.jsonl"), n))', '                    out.append((os.path.join(p, "runs", r, "events.jsonl"), n))\n                    out.append((os.path.join(p, "runs", r, "source", "fixtures", "audit", "events.jsonl"), n))')]),
    ("reservation_restored is summed", B, [('elif kind == "llm_call" and isinstance(cid, str)', 'elif kind in ("llm_call", "reservation_restored") and isinstance(cid, str)')]),
    ("a partial last line is consumed", B, [("                f.offset += cut + 1", "                f.offset += len(chunk)")]),
    ("a broken mid-file line makes the window unknown", B, [("        except (ValueError, UnicodeDecodeError):\n            return ", '        except (ValueError, UnicodeDecodeError):\n            f.final["__broken__"] = (None, None)\n            return ')]),
    ("an old unreadable ledger makes the month unknown", B, [("                    if f.unreadable_mtime >= m0:", "                    if True:")]),
    ("the zone is UTC-7", B, [("timezone(timedelta(hours=7))", "timezone(timedelta(hours=-7))")]),
    ("an append is not re-read", B, [("            if f.ino == st.st_ino and f.size == st.st_size and f.mtime_ns == st.st_mtime_ns:", "            if f.ino == st.st_ino:")]),
    ("a shrunk ledger is not re-read", B, [("            if f.ino != st.st_ino or st.st_size < f.offset:", "            if f.ino != st.st_ino:")]),
    ("only chat made jobs are listed", B, [('            elif n.startswith("j"):', '            elif n.startswith("j2026"):')]),
    ("the month meter sums the day", B, [("                    if in_month:\n                        month += nano", "                    if in_day:\n                        month += nano")]),
    ("the warning starts one nano late", B, [("spent_nano * 1_000_000 >= int(", "spent_nano * 1_000_000 > int(")]),
    ("a symlinked ledger is followed", B, [("os.O_RDONLY | os.O_NOFOLLOW", "os.O_RDONLY")]),
    ("the snapshot is never cached", B, [("t - self._cache[0] < BUDGET_TTL_S and", "False and")]),
    ("the reason is drawn as HTML", JS, [('card.appendChild(el("p", "note", "The spend of this " + (title === "Today" ? "day" : "month") + " cannot be computed (" + String(w.unknown && w.unknown.reason) + (w.unknown && w.unknown.job ? ", " + String(w.unknown.job) : "") + "). It is not zero."));',
                                          'var np = el("p", "note"); np.innerHTML = "cannot be computed (" + String(w.unknown && w.unknown.reason) + (w.unknown && w.unknown.job ? ", " + String(w.unknown.job) : "") + "). It is not zero."; card.appendChild(np);')]),
    ("the chip shows a non-number as a number", JS, [('if (b.day.unknown || typeof b.day.spent_usd !== "number") { return "Today ?"; }', 'if (b.day.unknown) { return "Today ?"; }')]),
    ("serve does not warm the ledgers", C, [("        actions.budget.warm()   ", "        pass   ")]),
]
killed = ran = 0
for name, f, edits in M:
    if ONLY and not any(o in name for o in ONLY):
        continue
    p = WT / f
    orig = p.read_text()
    text = orig
    if any(text.count(a) != 1 for a, _ in edits):
        print("STALE  ", name, [text.count(a) for a, _ in edits], flush=True)
        continue
    for a, b in edits:
        text = text.replace(a, b, 1)
    p.write_text(text)
    ran += 1
    try:
        r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", "-n0", *T], cwd=WT, capture_output=True, text=True, timeout=300,
                           env={**os.environ, "PYTHONPATH": f"{WT}:{WT}/scripts:{WT}/tests"})
        dead = r.returncode != 0
    except subprocess.TimeoutExpired:
        dead = True
    finally:
        p.write_text(orig)
    killed += dead
    print("killed " if dead else "SURVIVED", name, flush=True)
print(f"{killed}/{ran} killed")
