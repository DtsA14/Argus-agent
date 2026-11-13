"""Is the issue still open at its base? A mechanical check, no model (docs: pilots/outside_v1/PREFLIGHT.md). The maintainers' test files of the
fix PR (overlaid) are run in the Argus sandbox on the base tree and on the fix tree; the issue is VALID when at least one test fails on the base
and passes on the fix (fail-to-pass). Only counts and names of tests are printed; the fix and the tests are not read by anyone. Other
people's code runs only in the Docker sandbox (no network, read-only, nothing writable, user nobody).
usage: validity.py <repo-dir> <base-sha> <merge-sha> <runner: pytest|unittest>"""
import json
import os
import re
import subprocess
import sys
import tempfile

repo, base, merge, runner = os.path.expanduser(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4]
IMG = "sha256:3e48cd98c8de"


def sh(*a, **k):
    return subprocess.run(a, capture_output=True, text=True, **k)


def tree(rev, dest):
    os.makedirs(dest)
    p = subprocess.run(["git", "-C", repo, "archive", rev], capture_output=True, check=True)
    subprocess.run(["tar", "-x", "-C", dest], input=p.stdout, check=True)


files = sh("git", "-C", repo, "diff", "--name-only", base, merge).stdout.split()
tests = [f for f in files if re.match(r"(tests?/|.*/tests?/)", f) and f.endswith(".py")]


def run(root):
    if runner == "unittest":
        mods = [f[:-3].replace("/", ".") for f in tests]
        argv = ["python3", "-B", "-m", "unittest", "-v", *mods]
        env = ["-e", "PYTHONPATH=/workspace"]
    else:
        argv = ["python3", "-I", "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", "-o", "addopts=", "--rootdir", "/workspace", "-rA", "--tb=no", "-W", "ignore",
                *tests]
        env = []
    r = sh("docker", "run", "--rm", "--network", "none", "--read-only", "--cap-drop", "ALL", "--user", "65534:65534", "--memory", "512m", "--cpus", "1",
           "--pids-limit", "128", "--tmpfs", "/tmp:rw,size=64m,mode=1777", "-v", f"{root}:/workspace:ro", "-w", "/workspace",
           "-e", "PYTHONDONTWRITEBYTECODE=1", *env, IMG, *argv, timeout=900)
    txt = r.stdout + r.stderr
    res = {}
    if runner == "unittest":
        names = set(re.findall(r"^(test\w*) \(([\w.]+)\)", txt, re.M))
        bad = {(m.group(1), m.group(2)) for m in re.finditer(r"^(?:FAIL|ERROR): (test\w*) \(([\w.]+)\)", txt, re.M)}
        res = {c + "::" + n: ("FAILED" if (n, c) in bad else "PASSED") for n, c in names | bad}
        if not names and "Ran 0 tests" in txt:
            res = {}
    else:
        for line in txt.splitlines():
            m = re.match(r"(PASSED|FAILED|ERROR) (\S+)", line)
            if m:
                res[m.group(2)] = m.group(1)
    return res


work = tempfile.mkdtemp(prefix="validity_")
out = {"tests": tests}
for name, rev in (("base", base), ("fix", merge)):
    d = f"{work}/{name}"
    tree(rev if name == "fix" else base, d)
    if name == "base":
        for f in tests:                                  # the maintainers' version of each test file over the base tree
            c = sh("git", "-C", repo, "show", f"{merge}:{f}")
            if c.returncode == 0:
                os.makedirs(os.path.dirname(f"{d}/{f}"), exist_ok=True)
                open(f"{d}/{f}", "w").write(c.stdout)
            elif os.path.exists(f"{d}/{f}"):
                os.remove(f"{d}/{f}")
    out[name] = run(d)
b, f = out["base"], out["fix"]
f2p = sorted(n for n, s in f.items() if s == "PASSED" and b.get(n) != "PASSED")
p2p = sorted(n for n, s in f.items() if s == "PASSED" and b.get(n) == "PASSED")
print(json.dumps({"tests": tests, "base_ran": len(b), "fix_ran": len(f), "fix_not_passing": sorted(n for n, s in f.items() if s != "PASSED")[:3],
                  "f2p": len(f2p), "p2p": len(p2p), "valid": bool(f2p) and not [n for n, s in f.items() if s != "PASSED"], "f2p_sample": f2p[:3]}))
