"""Mutants for MAX-SUBMITS (config.yaml, router/job.py; SPEC_MAX_SUBMITS): each applied alone in a worktree, tests/test_submit_lines.py and
tests/test_drafter.py run with -x; killed = a test FAILED and pytest reported no error. Usage: <this> <worktree> <python>   (--check: only
count the patterns; --only <text>: only the mutants whose name has the text)"""
import os
import subprocess
import sys
from pathlib import Path

Y, J = "config.yaml", "router/job.py"
T = ["-rfEs", "tests/test_submit_lines.py", "tests/test_drafter.py"]
M = [
    ("the limit is five again", [(Y, "  max_submits: 7            # 3 until", "  max_submits: 5            # 3 until")]),
    ("the limit is eight", [(Y, "  max_submits: 7            # 3 until", "  max_submits: 8            # 3 until")]),
    ("the line is not printed", [(J, "    out += _attempt_lines(job)\n    out += _submit_lines(job)\n", "    out += _attempt_lines(job)\n")]),
    ("the line comes from the estimate instead of its own call", [(J, "    out += _submit_lines(job)\n    out += _estimate_lines(job)", "    out += _estimate_lines(job)")]),
    ("events are counted, not submits", [(J, "used = {e[\"submit\"] for e in evs if", "used = [e[\"submit\"] for e in evs if")]),
    ("a refused submit counts", [(J, "if e.get(\"event\") == \"draft_submitted\" and isinstance(e.get(\"submit\"), int)}", "if e.get(\"event\") in (\"draft_submitted\", \"draft_submit_refused\") and isinstance(e.get(\"submit\"), int)}")]),
    ("only an accepted submit counts", [(J, "if e.get(\"event\") == \"draft_submitted\" and isinstance(e.get(\"submit\"), int)}", "if e.get(\"event\") == \"draft_submitted\" and e.get(\"ok\") and isinstance(e.get(\"submit\"), int)}")]),
    ("a submit number that is not an int counts", [(J, "if e.get(\"event\") == \"draft_submitted\" and isinstance(e.get(\"submit\"), int)}", "if e.get(\"event\") == \"draft_submitted\"}")]),
    ("the limit is the step limit", [(J, "e[\"max_submits\"] for e in evs if e.get(\"event\") == \"drafter_policy\" and isinstance(e.get(\"max_submits\"), int)", "e[\"max_steps\"] for e in evs if e.get(\"event\") == \"drafter_policy\" and isinstance(e.get(\"max_steps\"), int)")]),
    ("an unknown limit is printed", [(J, "(f\" of {limit}\" if limit is not None else \"\")", "(f\" of {limit}\" if True else \"\")")]),
    ("the limit is never printed", [(J, "(f\" of {limit}\" if limit is not None else \"\")", "\"\"")]),
    ("every stage kind gets a line", [(J, "        if s.get(\"kind\") != \"draft\" or not s.get(\"run_id\"):\n            continue\n        try:\n            evs = parse_lines((job.runs / s[\"run_id\"] / \"events.jsonl\")", "        if not s.get(\"run_id\"):\n            continue\n        try:\n            evs = parse_lines((job.runs / s[\"run_id\"] / \"events.jsonl\")")]),
    ("a stage not started is read", [(J, "        if s.get(\"kind\") != \"draft\" or not s.get(\"run_id\"):\n            continue\n        try:\n            evs = parse_lines((job.runs / s[\"run_id\"] / \"events.jsonl\")", "        if s.get(\"kind\") != \"draft\":\n            continue\n        try:\n            evs = parse_lines((job.runs / s[\"run_id\"] / \"events.jsonl\")")]),
    ("the stages are sorted as text", [(J, "key=lambda kv: int(kv[0][1:]) if kv[0][1:].isdigit() else 0):", "key=lambda kv: kv[0]):")]),
    ("a file that cannot be read breaks the status", [(J, "        except OSError:\n            continue\n        evs = [e for e in evs if isinstance(e, dict)]", "        except ZeroDivisionError:\n            continue\n        evs = [e for e in evs if isinstance(e, dict)]")]),
    ("an event that is not an object breaks the status", [(J, "        evs = [e for e in evs if isinstance(e, dict)]\n", "")]),
    ("bytes that are not utf-8 break the status", [(J, "(job.runs / s[\"run_id\"] / \"events.jsonl\").read_text(encoding=\"utf-8\", errors=\"replace\"))\n        except OSError:\n            continue\n        evs = [e for e in evs if isinstance(e, dict)]", "(job.runs / s[\"run_id\"] / \"events.jsonl\").read_text(encoding=\"utf-8\"))\n        except OSError:\n            continue\n        evs = [e for e in evs if isinstance(e, dict)]")]),
]

if __name__ == "__main__":
    WT, PY = Path(sys.argv[1]), sys.argv[2]
    check_only = "--check" in sys.argv
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else ""
    todo = [m for m in M if only in m[0]]
    killed = 0
    for name, edits in todo:
        originals, texts = {}, {}
        for f, a, b in edits:
            texts.setdefault(f, (WT / f).read_text())
            originals.setdefault(f, texts[f])
            assert texts[f].count(a) == 1, (name, a[:70], texts[f].count(a))
            texts[f] = texts[f].replace(a, b, 1)
        if check_only:
            continue
        for f, t in texts.items():
            (WT / f).write_text(t)
        try:
            r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *T], cwd=WT,
                               capture_output=True, text=True, timeout=1800, env=os.environ)
        finally:
            for f, t in originals.items():
                (WT / f).write_text(t)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        fails = [line for line in r.stdout.splitlines() if line.startswith("FAILED tests/test_")][:1]
        k = bool(fails) and "error" not in last
        killed += k
        verdict = "KILLED  " if k else "SKIPPED " if "skipped" in last and not fails else "ERROR   " if "error" in last else "SURVIVED"
        print(f"{verdict} {name}: {fails or last}", flush=True)
    print("patterns ok" if check_only else f"RESULT: {killed}/{len(todo)} killed")
