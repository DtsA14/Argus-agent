"""Mutants for SPEC_VF_CANARY O2 (acceptance/testdetect.py forger patterns): each applied alone in a worktree; killed = a test failed
(an error or a skip is not a kill). Usage: forger_patterns_mutants.py <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
F = "acceptance/testdetect.py"
TESTS = ["tests/test_test_detection.py", "tests/test_detection_terminal.py"]
M = [
    ("os._exit not matched", F, '"os._exit": (re.compile(r"\\b_exit\\s*\\("),),', '"os._exit": (re.compile(r"\\bNEVER_MATCHES\\b"),),'),
    ("os._exit without the word boundary", F, 'r"\\b_exit\\s*\\("', 'r"_exit\\s*\\("'),
    ("os._exit needs a space", F, 'r"\\b_exit\\s*\\("', 'r"\\b_exit\\s+\\("'),
    ("os.abort not matched", F, 'r"\\bos\\.abort\\s*\\("', 'r"\\bNEVER_MATCHES\\b"'),
    ("self-kill not matched", F, 'r"\\bos\\.kill\\(\\s*os\\.getpid\\(\\)"', 'r"\\bNEVER_MATCHES\\b"'),
    ("raw fd: only descriptor 1", F, "(?:[12]|sys", "(?:[1]|sys"),
    ("raw fd: only descriptor 2", F, "(?:[12]|sys", "(?:[2]|sys"),
    ("raw fd: no sys.stdout.fileno", F, "(?:[12]|sys\\.\\w*(?:stdout|stderr)\\w*\\.fileno\\(\\))", "(?:[12])"),
    ("raw fd: any write", F, r'r"\bos\.write\(\s*(?:[12]|sys\.\w*(?:stdout|stderr)\w*\.fileno\(\))\s*,"', r'r"\bos\.write\("'),
    ("S_ISFIFO not matched", F, '"S_ISFIFO": (re.compile(r"S_ISFIFO"),),', '"S_ISFIFO": (re.compile(r"NEVER_MATCHES"),),'),
    ("/proc/self not matched", F, '"/proc/self": (re.compile(r"/proc/self\\b"),),', '"/proc/self": (re.compile(r"NEVER_MATCHES"),),'),
    ("/proc/self without the boundary", F, 'r"/proc/self\\b"', 'r"/proc/self"'),
    ("forgers not in the scan", F, "PATTERNS = {**PATTERNS, **FORGERS}", "PATTERNS = {**PATTERNS}"),
    ("no forging flag on the hit", F, '**({"forging": True} if _forging(line) else {})', "**{}"),
    ("the flag is set for every hit", F, '**({"forging": True} if _forging(line) else {})', '**({"forging": True} if line else {})'),
    ("the reason ignores the flag", F, 'any(e.get("forging") for e in found)', "False"),
    ("the reason always says forging", F, 'any(e.get("forging") for e in found)', "bool(found)"),
    ("the reason wording", F, '" or can forge the test report"', '" or something"'),
]

if __name__ == "__main__":
    killed = 0
    for name, f, old, new in M:
        p = WT / f
        orig = p.read_text()
        assert orig.count(old) == 1, (name, orig.count(old))
        p.write_text(orig.replace(old, new, 1))
        r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *TESTS], cwd=WT, capture_output=True, text=True)
        p.write_text(orig)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        k = "failed" in last
        killed += k
        fails = [line for line in r.stdout.splitlines() if line.startswith("FAILED")][:1]
        print(f"{'KILLED ' if k else 'SURVIVED'} {name}: {fails or last}", flush=True)
    print(f"RESULT: {killed}/{len(M)} killed")
