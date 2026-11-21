"""Mutants for the chat's research key slot (router/chat_actions.py, ARGUS_CHAT_RESEARCH_KEY_FILE): applied alone; killed = a test FAILED.
Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
F = "router/chat_actions.py"
T = ["-rfEs", "tests/test_chat_research.py", "tests/test_chat_actions.py"]
M = [
    ("research is given the code key only", [('research=(a == "research_new"))', "research=False)")]),
    ("every action is given the research key", [('first = WRITER_KEY_ENV if writer else RESEARCH_KEY_ENV if research else None\n        return', 'first = WRITER_KEY_ENV if writer else RESEARCH_KEY_ENV\n        return')]),
    ("the research key does not fall back to the code key", [('or self.environ.get(KEY_ENV) or None', 'or None')]),
    ("the research check asks for the code key", [("self._need_key(False, research=True)", "self._need_key(False)")]),
    ("the writer turn gets the research key", [("first = WRITER_KEY_ENV if writer else RESEARCH_KEY_ENV if research else None\n        return", "first = RESEARCH_KEY_ENV if writer else None\n        return")]),
]
killed = 0
for name, edits in M:
    p = WT / F
    orig = p.read_text()
    text = orig
    if any(text.count(a) != 1 for a, _ in edits):
        print("STALE  ", name, flush=True)
        continue
    for a, b in edits:
        text = text.replace(a, b, 1)
    p.write_text(text)
    try:
        r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", "-n", "4", *T], cwd=WT, capture_output=True, text=True, timeout=900)
    finally:
        p.write_text(orig)
    last = (r.stdout.strip().splitlines() or [""])[-1]
    k = "FAILED tests/" in r.stdout and "error" not in last
    killed += k
    print("KILLED " if k else "SURVIVED", name, flush=True)
print(f"RESULT: {killed}/{len(M)} killed")
