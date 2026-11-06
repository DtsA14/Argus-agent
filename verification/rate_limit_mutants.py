"""Mutants for SPEC_RATE_LIMIT_RETRY (harness/llm.py): each applied alone in a worktree, the named tests run with -x;
killed = a test FAILED and pytest reported no error (an import or fixture error, or a skip, is not a kill).
Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
L = "harness/llm.py"
T = ["-rfEs", "tests/test_rate_limit_retry.py", "tests/test_gateway.py", "tests/test_free_fallbacks.py"]
M = [
    # G1 / R1
    ("a 429 waits base_delay", L, [("delay, top = (self.rl_delay, self.rl_max) if rate else",
                                    "delay, top = (self.base_delay, self.rl_max) if rate else")]),
    ("the 120 s bound dropped", L, [("        return min(wait, top)\n", "        return wait\n")]),
    # G2
    ("Retry-After not bounded", L, [("        if wait is None:\n            wait = delay * 2 ** (n - 1) * (0.5 + random.random())\n        return min(wait, top)",
                                     "        if wait is not None:\n            return wait\n        wait = delay * 2 ** (n - 1) * (0.5 + random.random())\n        return min(wait, top)")]),
    ("a bad Retry-After is used", L, [("if wait is not None and not (math.isfinite(wait) and wait >= 0):", "if False:")]),
    # G3
    ("a 500 waits like a 429", L, [("        rate = self._rate_limited(exc)\n", "        rate = is_transient(exc)\n")]),
    # G4
    ("rate_limit_attempts ignored", L, [("if n >= (self.rl_attempts if rate else self.attempts):", "if n >= self.attempts:")]),
    ("one counter for both kinds", L, [("        seen[kind] += 1\n        n = seen[kind]\n",
                                        "        seen[\"rate\"] += 1\n        n = seen[\"rate\"]\n")]),
    ("a status-less rate limit is not one", L, [(' or (status is None and "ratelimit" in type(exc).__name__.lower())', "")]),
    ("a free model waits long", L, [('        if self.gateway is not None and self.gateway["free"]:\n            return False\n',
                                     "")]),
    # G5 / G6
    ("a paid gateway 429 charged worst case", L, [("if self.gateway is not None and status_code == 429:",
                                                    'if self.gateway is not None and self.gateway["free"] and status_code == 429:')]),
    ("a direct 429 charged 0", L, [("if self.gateway is not None and status_code == 429:", "if status_code == 429:")]),
    ("any gateway error charged 0", L, [("if self.gateway is not None and status_code == 429:", "if self.gateway is not None:")]),
    # G8
    ("an infinite delay accepted", L, [("not math.isfinite(v) or ", "")]),
    ("max below delay accepted", L, [("    if top < delay:\n", "    if False:\n")]),
    ("attempts not checked", L, [('for name, v in (("attempts", attempts), ("rate_limit_attempts", rl_attempts)):',
                                  'for name, v in (("rate_limit_attempts", rl_attempts),):')]),
    ("config.yaml defaults changed", "config.yaml", [("  rate_limit_attempts: 4\n", "  rate_limit_attempts: 3\n")]),
]

if __name__ == "__main__":
    killed = 0
    for name, f, edits in M:
        p = WT / f
        orig = p.read_text()
        text = orig
        for a, b in edits:
            assert text.count(a) == 1, (name, a[:50], text.count(a))
            text = text.replace(a, b, 1)
        p.write_text(text)
        try:
            r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *T], cwd=WT,
                               capture_output=True, text=True, timeout=1800)
        finally:
            p.write_text(orig)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        fails = [line for line in r.stdout.splitlines() if line.startswith("FAILED tests/")][:1]
        k = bool(fails) and "error" not in last
        killed += k
        verdict = "KILLED " if k else "SKIPPED" if "skipped" in last else "ERROR  " if "error" in last else "SURVIVED"
        print(f"{verdict} {name}: {fails or last}", flush=True)
    print(f"RESULT: {killed}/{len(M)} killed")
