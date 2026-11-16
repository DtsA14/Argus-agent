"""Mutants for SPEC_PRD_WRITER 11c (the touch/creates rules told to the writer: prompt, schema, hint in codetask/prd_writer.py): each applied alone in a worktree; killed = a test FAILED and pytest reported no error.
Usage: <this> <worktree> <python> [name fragments to run only some]. Docker is not needed.
"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
ONLY = sys.argv[3:]
T = ["-rfEs", "tests/test_prd_writer.py", "tests/test_prd_writer_base.py"]
PW = "codetask/prd_writer.py"


M = [
    ("the hint is dropped", PW, [("                    if best:\n", "                    if False:\n")]),
    ("the hint names the item's own creates", PW, [("best = _created_name_near(t.strip(), known)", 'best = _created_name_near(t.strip(), known | set(shape["creates"]))')]),
    ("the hint also names names created later", PW, [("best = _created_name_near(t.strip(), known)", "best = _created_name_near(t.strip(), known | later)")]),
    ("the near hint overrides the later hint", PW, [("                elif isinstance(t, str) and f\"touch {t.strip()!r}\" in p:\n                    best =", "                if isinstance(t, str) and f\"touch {t.strip()!r}\" in p:\n                    best =")]),
    ("the touch is not stripped for the hint", PW, [("best = _created_name_near(t.strip(), known)", "best = _created_name_near(t, known)")]),
    ("the hint is an order, not a condition", PW, [('(if you mean the {best!r} that an earlier item creates, write', '(an earlier item creates {best!r}: write')]),
    ("the shortest name inside the touch wins", PW, [("return max(inside, key=len)", "return min(inside, key=len)")]),
    ("the first name alphabetically wins", PW, [("return max(inside, key=len)", "return inside[0]")]),
    ("a name inside a longer word counts", PW, [('r"(?<!\\w)" + re.escape(n) + r"(?!\\w)"', 're.escape(n)')]),
    ("the longest abbreviated name wins", PW, [("return min(around, key=len) if around else None", "return max(around, key=len) if around else None")]),
    ("a touch under four characters matches inside a name", PW, [("len(touch) >= 4 and touch in n", "touch in n")]),
    ("the abbreviation direction is dropped", PW, [("    around = sorted(n for n in known if len(touch) >= 4 and touch in n)", "    around = []")]),
    ("the prompt forgets the touch length", PW, [('f"Each touch is ONE line of {iw.TOUCH_MIN} to {iw.TOUCH_MAX} characters: a name', 'f"Each touch is ONE line: a name')]),
    ("the prompt forgets the creates length", PW, [('f"line of {iw.TOUCH_MIN} to {iw.TOUCH_MAX} "\n    "characters, for example', 'f"line "\n    "characters, for example')]),
    ("the prompt forgets the creates count", PW, [('f"- `creates`: at most {CREATES_MAX} SHORT NAMES', 'f"- `creates`: SHORT NAMES')]),
    ("the prompt forgets the exact match", PW, [("(the harness matches EXACTLY, not by substring)", "(the harness matches names)")]),
    ("the prompt allows signatures", PW, [("never a signature. A LATER item", "or a signature. A LATER item")]),
    ("the prompt forgets that a long touch is refused", PW, [("(a longer text is refused)", "")]),
    ("the prompt forgets ONE line for touches", PW, [("Each touch is ONE line of", "Each touch is a line of")]),
    ("the schema forgets the touch length", PW, [('f"{iw.TOUCH_MIN} to {iw.TOUCH_MAX} characters (a name or a short code fragment, never a whole "', '"characters (a name or a short code fragment, never a whole "')]),
    ("the schema forgets the signature rule for touches", PW, [('(a name or a short code fragment, never a whole "\n                               "signature or a sentence)', '(a name or a short code fragment)')]),
    ("the schema forgets character for character", PW, [('"character for character as an EARLIER item wrote it in its `creates`.")', '"as an EARLIER item wrote it in its `creates`.")')]),
    ("the schema's creates forgets the length", PW, [('f"{iw.TOUCH_MAX} characters, one line: `budget_rows`', 'f"characters, one line: `budget_rows`')]),
    ("the schema's creates forgets the count", PW, [('description=f"At most {CREATES_MAX} short names (', 'description=f"Short names (')]),
    ("the schema's creates allows signatures", PW, [("`/scoreboard/jobs`, never a signature)", "`/scoreboard/jobs`)")]),
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
