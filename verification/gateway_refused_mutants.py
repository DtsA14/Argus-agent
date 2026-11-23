"""Mutants for SPEC_GATEWAY_REFUSED_FREE (harness/llm.py): each applied alone in a worktree; killed = a test FAILED and pytest reported no error.
The list is the reviewer's (Opus, 2026-11-23), cut to the ones that can be written as a single edit. Usage: <this> <worktree> <python> [name fragments]."""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
ONLY = sys.argv[3:]
L = "harness/llm.py"
T = ["-rfEs", "tests/test_provider_failure_reason.py", "tests/test_gateway.py", "tests/test_rate_limit_retry.py"]
GUARD = "if self.gateway is not None and status_code in GATEWAY_REFUSED:"
M = [
    ("the refused statuses lose 401", L, [("GATEWAY_REFUSED = (401, 402, 429)", "GATEWAY_REFUSED = (402, 429)")]),
    ("the refused statuses lose 402", L, [("GATEWAY_REFUSED = (401, 402, 429)", "GATEWAY_REFUSED = (401, 429)")]),
    ("the refused statuses lose 429", L, [("GATEWAY_REFUSED = (401, 402, 429)", "GATEWAY_REFUSED = (401, 402)")]),
    ("the refused statuses gain 403", L, [("GATEWAY_REFUSED = (401, 402, 429)", "GATEWAY_REFUSED = (401, 402, 403, 429)")]),
    ("the refused statuses gain 408", L, [("GATEWAY_REFUSED = (401, 402, 429)", "GATEWAY_REFUSED = (401, 402, 408, 429)")]),
    ("the refused statuses gain 500", L, [("GATEWAY_REFUSED = (401, 402, 429)", "GATEWAY_REFUSED = (401, 402, 429, 500)")]),
    ("the refused statuses gain None", L, [("GATEWAY_REFUSED = (401, 402, 429)", "GATEWAY_REFUSED = (401, 402, 429, None)")]),
    ("a direct provider is free too", L, [(GUARD, "if status_code in GATEWAY_REFUSED:")]),
    ("only a direct provider is free", L, [(GUARD, "if self.gateway is None and status_code in GATEWAY_REFUSED:")]),
    ("the tokens stay charged", L, [("                    tok, nano = 0, 0\n\n                try:", "                    tok, nano = tok, 0\n\n                try:")]),
    ("the dollars stay charged", L, [("                    tok, nano = 0, 0\n\n                try:", "                    tok, nano = 0, nano\n\n                try:")]),
    ("the row says worst case", L, [('charged="worst_case" if tok else "none",', 'charged="worst_case",')]),
    ("the reservation is charged the worst case", L, [("                finally:\n                    reservation.charge(tok, nano)", "                finally:\n                    reservation.charge(worst_tokens, worst_nano)")]),
    ("a 402 is transient", L, [("TRANSIENT_STATUS = {408, 409, 425, 429}", "TRANSIENT_STATUS = {402, 408, 409, 425, 429}")]),
    ("a string status counts", L, [("    return status if isinstance(status, int) else None", "    return int(status) if str(status).isdigit() else None")]),
    ("the response status wins", L, [('status = getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", None)',
                                      'status = getattr(getattr(exc, "response", None), "status_code", None) or getattr(exc, "status_code", None)')]),
    ("the delivery of a refusal is unknown", L, [('delivery="received" if status_code else "unknown"', 'delivery="unknown"')]),
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
            r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *T], cwd=WT, capture_output=True, text=True, timeout=600)
        finally:
            p.write_text(orig)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        fails = [line for line in r.stdout.splitlines() if line.startswith("FAILED tests/test_")][:1]
        k = bool(fails) and "error" not in last
        killed += k
        print(f"{'KILLED ' if k else 'ERROR  ' if 'error' in last else 'SURVIVED'} {name}: {fails or last}", flush=True)
    print(f"RESULT: {killed}/{ran} killed")
