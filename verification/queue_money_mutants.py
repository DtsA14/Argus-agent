"""Mutants for SPEC_QUEUE_MONEY (router/queue.py, router/cards.py): each applied alone in a worktree; killed = a test FAILED and pytest reported no error.
Usage: <this> <worktree> <python> [name fragments]."""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
ONLY = sys.argv[3:]
Q, C = "router/queue.py", "router/cards.py"
T = ["-rfEs", "tests/test_queue.py", "tests/test_chat_cards.py"]
SO = "SPENT_ONLY = (rj.ABANDONED, rj.BLOCKED, rj.REVIEW_INVALID, rj.APPLIED)"


def off(cond):
    return (cond, cond[: len(cond) - len(cond.lstrip())] + "if False:")


M = [
    ("APPLIED is held at its cap again", Q, [(SO, "SPENT_ONLY = (rj.ABANDONED, rj.BLOCKED, rj.REVIEW_INVALID)")]),
    ("APPLIED holds nothing", Q, [("    return rj.spent_nano(job) if job.data[\"state\"] in SPENT_ONLY else to_nano(job.data[\"max_usd\"])", "    return 0 if job.data[\"state\"] == rj.APPLIED else rj.spent_nano(job) if job.data[\"state\"] in SPENT_ONLY else to_nano(job.data[\"max_usd\"])")]),
    ("REJECTED joins the spent-only states", Q, [(SO, "SPENT_ONLY = (rj.ABANDONED, rj.BLOCKED, rj.REVIEW_INVALID, rj.APPLIED, rj.REJECTED)")]),
    ("a failed job joins the spent-only states", Q, [(SO, "SPENT_ONLY = (rj.ABANDONED, rj.BLOCKED, rj.REVIEW_INVALID, rj.APPLIED, rj.AGENT_FAILED)")]),
    ("the card holds only the cap", C, [("        if job.get(\"state\") in rq.SPENT_ONLY:\n            spent = self._spent(job)", "        if False:\n            spent = self._spent(job)")]),
    ("the card counts an unknown cost as zero", C, [("            return to_nano(spent) if spent is not None else cap", "            return to_nano(spent) if spent is not None else 0")]),
    ("the money stop is not made", C, [off("                if cap > left:")]),
    ("the money stop has no next step", C, [("\"Tidak ada perintah yang menambah uang antrean: tutup antrean ini dan buat antrean baru untuk issue yang tersisa (di terminal)\"", "\"\"")]),
    ("a REJECTED job with retries left says redo from the PRD", C, [("            if len(item.get(\"retries\") or []) < rq.MAX_RETRIES:", "            if False:")]),
    ("a REJECTED job with no retries left says retry", C, [("            if len(item.get(\"retries\") or []) < rq.MAX_RETRIES:", "            if True:")]),
    ("the default hint is dropped", C, [("        return f\"Lihat: argus status {j} (di terminal)\"", "        return \"\"")]),
    ("the stopped hint is not appended", C, [(". \" + self._stopped_hint(q, item, job, st)", ". \"")]),
    ("the unbound-job line loses its next step", C, [("bukan issue antrean ini di commit ini. Lihat: argus status {self.s(job.get('job'))} (di terminal)", "bukan issue antrean ini di commit ini")]),
    ("an applied job that is not the patch loses its next step", C, [("tidak tercatat sebagai patch. Lihat: argus status {self.s(job.get('job'))} (di terminal)", "tidak tercatat sebagai patch")]),
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
            r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", "-n", "4", *T], cwd=WT, capture_output=True, text=True, timeout=1800)
        finally:
            p.write_text(orig)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        fails = [line for line in r.stdout.splitlines() if line.startswith("FAILED tests/test_")][:1]
        k = bool(fails) and "error" not in last
        killed += k
        print(f"{'KILLED ' if k else 'ERROR  ' if 'error' in last else 'SURVIVED'} {name}: {fails or last}", flush=True)
    print(f"RESULT: {killed}/{ran} killed")
