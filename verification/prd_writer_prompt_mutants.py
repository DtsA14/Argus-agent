"""Mutants for SPEC_PRD_WRITER 11c (the touch/creates rules told to the writer: prompt, schema, hint in codetask/prd_writer.py): each applied alone in a worktree; killed = a test FAILED and pytest reported no error.
Usage: <this> <worktree> <python> [name fragments to run only some]. Docker is not needed.
"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
ONLY = sys.argv[3:]
T = ["-rfEs", "tests/test_prd_writer.py", "tests/test_prd_writer_base.py"]
PW, PJ, IW, J, SB, CA = "codetask/prd_writer.py", "router/prd_job.py", "codetask/issue_writer.py", "router/job.py", "scripts/scoreboard.py", "router/chat_actions.py"


def off(cond):
    """The condition's line with `if False:` in its place, keeping the indentation."""
    return (cond, cond[: len(cond) - len(cond.lstrip())] + "if False:")


M = [
    ("the creates hint is dropped", PW, [("                    if near:\n", "                    if False:\n")]),
    ("the hint names the item's own creates", PW, [("near = sorted(n for n in known if n and", 'near = sorted(n for n in known | set(shape["creates"]) if n and')]),
    ("the hint works one way only", PW, [("(n in t.strip() or t.strip() in n)", "(n in t.strip())")]),
    ("the hint is given for a later-created name too", PW, [("                elif isinstance(t, str) and f\"touch {t.strip()!r}\" in p:\n                    near =", "                elif isinstance(t, str) and f\"touch {t.strip()!r}\" in p and t.strip() not in later and False:\n                    near =")]),
    ("the prompt forgets the touch length", PW, [("Each touch is ONE line of 2 to 80 characters: a name", "Each touch is ONE line: a name")]),
    ("the prompt forgets the creates length", PW, [("each one line of 2 to 80 \"\n    \"characters, for example", "each one line \"\n    \"characters, for example")]),
    ("the prompt forgets the exact match", PW, [("(the harness matches EXACTLY, not by substring)", "(the harness matches names)")]),
    ("the prompt allows signatures", PW, [("never a signature. A LATER item", "or a signature. A LATER item")]),
    ("the schema forgets the touch length", PW, [('f"{iw.TOUCH_MIN} to {iw.TOUCH_MAX} characters (a name or a short code fragment, never a whole "', '"characters (a name or a short code fragment, never a whole "')]),
    ("the schema forgets character for character", PW, [('"character for character as an EARLIER item wrote it in its `creates`.")', '"as an EARLIER item wrote it in its `creates`.")')]),
    ("the schema's creates forgets the length", PW, [('f"Short names ({iw.TOUCH_MIN} to {iw.TOUCH_MAX} characters, "', '"Short names ("')]),
]

if __name__ == "__main__":
    killed = ran = 0
    for name, F, edits in M:
        if ONLY and not any(o in name for o in ONLY):
            continue
        p = WT / F
        orig = p.read_text()
        text = orig
        stale = [a[:70] for a, _ in edits if text.count(a) != 1]
        if stale:
            print(f"STALE   {name}: {stale}", flush=True)
            continue
        for a, b in edits:
            text = text.replace(a, b, 1)
        p.write_text(text)
        ran += 1
        try:
            r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *T], cwd=WT, capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired:
            print(f"TIMEOUT {name}", flush=True)
            continue
        finally:
            p.write_text(orig)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        fails = [line for line in r.stdout.splitlines() if line.startswith("FAILED tests/test_")][:1]
        k = bool(fails) and "error" not in last
        killed += k
        print(f"{'KILLED ' if k else 'ERROR  ' if 'error' in last else 'SURVIVED'} {name}: {fails or last}", flush=True)
    print(f"RESULT: {killed}/{ran} killed")
