"""Mutants for T6 PR1 (scripts/build_env_from_base.sh: wheels only, named index, isolated pip). Applied alone; killed = a test FAILED.
Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
F = "scripts/build_env_from_base.sh"
T = ["-rfEs", "tests/test_env_from_base.py", "-k", "wheels_only or wheel_with_its_hash or unpinned or pinned_definition"]
LINE = "--require-hashes --only-binary :all: \\\n           --index-url https://pypi.org/simple --cache-dir /cache"
M = [
    ("the sdist guard is dropped", [("--require-hashes --only-binary :all: \\\n           --index-url", "--require-hashes \\\n           --index-url")]),
    ("only some packages are wheel-only", [("--require-hashes --only-binary :all: \\\n", "--require-hashes --only-binary pytest \\\n")]),
    ("the index is not named", [("           --index-url https://pypi.org/simple --cache-dir /cache", "           --cache-dir /cache")]),
    ("the index is plain http", [("--index-url https://pypi.org/simple", "--index-url http://pypi.org/simple")]),
    ("the index is another host", [("--index-url https://pypi.org/simple", "--index-url https://pypi.example.org/simple")]),
    ("pip reads its configuration and environment", [("pip --isolated install", "pip install")]),
    ("hashes are not required", [("--no-compile --require-hashes --only-binary", "--no-compile --only-binary")]),
    ("dependencies are resolved", [("install -q --no-deps --no-compile", "install -q --no-compile")]),
    ("the guard comes after the requirements file", [("--require-hashes --only-binary :all: \\\n           --index-url https://pypi.org/simple --cache-dir /cache --target /out/site \\\n           -r /def/requirements.txt", "--require-hashes --cache-dir /cache --target /out/site \\\n           -r /def/requirements.txt --only-binary :all: --index-url https://pypi.org/simple")]),
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
        r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *T], cwd=WT, capture_output=True, text=True, timeout=600)
    finally:
        p.write_text(orig)
    last = (r.stdout.strip().splitlines() or [""])[-1]
    k = "FAILED tests/" in r.stdout or "FAILED" in last
    killed += k
    print("KILLED " if k else "SURVIVED", name, flush=True)
print(f"RESULT: {killed}/{len(M)} killed")
