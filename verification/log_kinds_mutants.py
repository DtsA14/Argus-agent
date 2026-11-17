"""Mutants for the snapshot log kinds fix (router/stage_data.py LOG_WHAT and LOG_FIELDS): each applied alone in a worktree; killed = a test FAILED and pytest reported no error.
Usage: <this> <worktree> <python> [name fragments to run only some]. Docker is not needed.
"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
ONLY = sys.argv[3:]
T = ["-rfEs", "tests/test_stage_data_log_kinds.py", "tests/test_stage_data.py"]




M = [
    ('repro is not allowed again', 'router/stage_data.py', [('"repro", "repro_patched", "apply_started", "not_confirmed"}', '"repro_patched", "apply_started", "not_confirmed"}')]),
    ('repro_patched is not allowed again', 'router/stage_data.py', [('"repro", "repro_patched", "apply_started", "not_confirmed"}', '"repro", "apply_started", "not_confirmed"}')]),
    ('apply_started is not allowed again', 'router/stage_data.py', [('"repro", "repro_patched", "apply_started", "not_confirmed"}', '"repro", "repro_patched", "not_confirmed"}')]),
    ('not_confirmed is not allowed again', 'router/stage_data.py', [('"repro", "repro_patched", "apply_started", "not_confirmed"}', '"repro", "repro_patched", "apply_started"}')]),
    ('a core kind is dropped', 'router/stage_data.py', [('"key_from_file", "retry", "redraft",', '"key_from_file", "redraft",')]),
    ('the repro payload sid is published', 'router/stage_data.py', [('"stage": _pat(STAGE)}', '"stage": _pat(STAGE), "sid": None}')]),
    ('the repro payload blocks is published', 'router/stage_data.py', [('"stage": _pat(STAGE)}', '"stage": _pat(STAGE), "blocks": None}')]),
    ('the apply payload head is published', 'router/stage_data.py', [('"stage": _pat(STAGE)}', '"stage": _pat(STAGE), "head_before": None}')]),
    ('the apply payload examples_failed is published', 'router/stage_data.py', [('"stage": _pat(STAGE)}', '"stage": _pat(STAGE), "examples_failed": None}')]),
    ('an unknown kind no longer excludes', 'router/stage_data.py', [('"what": lambda v: v in LOG_WHAT,', '"what": lambda v: isinstance(v, str),')]),
]

if __name__ == "__main__":
    killed = ran = 0
    for name, F, edits, *rest in M:
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
            r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *(rest[0] if rest else T)], cwd=WT, capture_output=True, text=True, timeout=300)
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
