"""Mutants for SPEC_STANDALONE_H (install card check (h) for a job that is not a queue item). Applied alone; killed = a test FAILED.
Run in a throwaway worktree. Usage: <this> <worktree> <python> [name-part ...]"""
import os
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
ONLY = sys.argv[3:]
E, A = "router/examples_read.py", "router/approve_code.py"
T = ["tests/test_approve_code.py", "tests/test_chat_apply_reply.py"]
NQ = 'the job is not an item of a PRD queue", **({"standalone": True} if missing else {}))'
NI = 'the job is not an item of a queue of this jobs directory", standalone=True)'
H = 'elif res.get("standalone") is True:'
M = [
    ("chain: no key on the no-queues-dir result", E, [(NQ, 'the job is not an item of a PRD queue")')], T),
    ("chain: no key on the not-in-any-queue result", E, [(NI, 'the job is not an item of a queue of this jobs directory")')], T),
    ("chain: not-from-PRD result carries the key", E, [('"the queue was not made from a PRD folder")', '"the queue was not made from a PRD folder", standalone=True)')], T),
    ("chain: no-examples-block result carries the key", E, [('"the queue item\'s issue has no examples block")', '"the queue item\'s issue has no examples block", standalone=True)')], T),
    ("chain: default key in _chain_result", E, [('return {"applicable": applicable, "ok": ok, "kind": kind, "why": why, "rec": None, "prd_job": None, "item": None, **more}', 'return {"applicable": applicable, "ok": ok, "kind": kind, "why": why, "rec": None, "prd_job": None, "item": None, "standalone": True, **more}')], T),
    ("chain: an unopenable queues dir counts as missing", E, [('            missing = False                                     # it is there but cannot be opened: not "no queues" (F36)', '            missing = True')], T),
    ("chain: any OSError counts as missing", E, [('        except OSError:\n            missing = False', '        except OSError:\n            missing = True')], T),
    # "truthy instead of is True" is equivalent: the key is only ever True or absent, so it is not listed.
    ("h: null for any non-applicable result", A, [(H, 'elif not res["applicable"]:')], T),
    ("h: null before the defects check", A, [('            if item.get("unreadable") or item.get("defects"):\n                checks["h"]', '            if res.get("standalone") is True:\n                checks["h"] = _chk("h", None, "tidak berlaku: bukan item antrean PRD")\n            elif item.get("unreadable") or item.get("defects"):\n                checks["h"]')], T),
    ("h: null replaces the true branch", A, [('            elif counts["after"] + counts["whatif"] >= 1:\n                checks["h"] = _chk("h", True, "ada contoh perilaku baru")\n', '')], T),
    ("h: standalone gives true, not null", A, [('checks["h"] = _chk("h", None, "tidak berlaku: job ini bukan', 'checks["h"] = _chk("h", True, "tidak berlaku: job ini bukan')], T),
    ("h: the null has no reason", A, [('"tidak berlaku: job ini bukan item antrean PRD, tidak ada kartu rencana yang bisa memuat contoh; "\n                                              "yang menjaga: dua pembaca patch dan Anda membaca seluruh patch"', '""')], T),
    ("h: the false text is dropped", A, [('"tidak ada contoh untuk perilaku yang baru; pernyataan', '"pernyataan')], T),
]
killed = ran = 0
for name, f, edits, tests in M:
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
        r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *tests], cwd=WT, capture_output=True, text=True, timeout=240,
                           env={**os.environ, "PYTHONPATH": f"{WT}:{WT}/scripts:{WT}/tests"})
        dead = r.returncode != 0
    except subprocess.TimeoutExpired:
        dead = True
    finally:
        p.write_text(orig)
    killed += dead
    print("killed " if dead else "SURVIVED", name, flush=True)
print(f"{killed}/{ran} killed")
