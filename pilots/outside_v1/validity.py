"""Is the issue still open at its base? A mechanical check, no model (docs: pilots/outside_v1/PREFLIGHT.md). The maintainers' test files of the
fix PR (overlaid) are run in the Argus sandbox on the base tree and on the fix tree; the issue is VALID when at least one test fails on the base
and passes on the fix (fail-to-pass). v2 (2026-11-13, Fable's rule): the fail-to-pass tests that count are the ones the PR ADDED (their
ids do not exist when the base's own test files run on the base); an issue is `valid` only when at least one added test fails on the base and passes
on the fix and nothing else of those files fails on the fix; when every such test fails on the base because a name is missing (ImportError,
ModuleNotFoundError, AttributeError, NameError: the feature's API is absent at the base) the group is `rubric_only` (graded by the rubric, not by
the maintainers' tests: the issue may name the API differently from the fix). Only counts and names of tests are printed; the fix and the tests are not read by anyone. Other
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


def run(root, only=None):
    files_ = tests if only is None else only
    if runner == "unittest":
        mods = [f[:-3].replace("/", ".") for f in files_]
        argv = ["python3", "-B", "-m", "unittest", "-v", *mods]
        env = ["-e", "PYTHONPATH=/workspace"]
    else:
        argv = ["python3", "-I", "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", "-o", "addopts=", "--rootdir", "/workspace", "-rA", "--tb=no", "-W", "ignore",
                *files_]
        env = []
    r = sh("docker", "run", "--rm", "--network", "none", "--read-only", "--cap-drop", "ALL", "--user", "65534:65534", "--memory", "512m", "--cpus", "1",
           "--pids-limit", "128", "--tmpfs", "/tmp:rw,size=64m,mode=1777", "-v", f"{root}:/workspace:ro", "-w", "/workspace",
           "-e", "PYTHONDONTWRITEBYTECODE=1", "-e", "COLUMNS=600", *env, IMG, *argv, timeout=900)
    txt = r.stdout + r.stderr
    res, why = {}, {}
    if runner == "unittest":
        names = set(re.findall(r"^(test\w*) \(([\w.]+)\)", txt, re.M))
        bad = {(m.group(1), m.group(2)) for m in re.finditer(r"^(?:FAIL|ERROR): (test\w*) \(([\w.]+)\)", txt, re.M)}
        res = {c + "::" + n: ("FAILED" if (n, c) in bad else "PASSED") for n, c in names | bad}
        if not names and "Ran 0 tests" in txt:
            res = {}
        for blk in re.split(r"^={70}$", txt, flags=re.M):                 # one block per ERROR/FAIL: its last exception line
            h = re.match(r"\s*(ERROR|FAIL): (test\w*) \(([\w.]+)\)", blk)
            if h:
                last = [l for l in blk.splitlines() if re.match(r"^\w+(\.\w+)*(Error|Exception)\b", l)]
                why[h.group(3) + "::" + h.group(2)] = (last[-1] if last else ("AssertionError" if h.group(1) == "FAIL" else "Error"))
        for m in re.finditer(r"^ERROR: (\w[\w.]*) \(unittest\.loader\._FailedTest", txt, re.M):   # a module that did not import
            why["MODULE::" + m.group(1)] = "ImportError: module did not import"
    else:
        for line in txt.splitlines():
            m = re.match(r"(PASSED|FAILED|ERROR) (\S+)(?: - (.*))?", line)
            if m:
                res[m.group(2)] = m.group(1)
                if m.group(3):
                    why[m.group(2)] = m.group(3)
    return res, why


work = tempfile.mkdtemp(prefix="validity_")
out, whys = {"tests": tests}, {}
EXISTING = [f for f in tests if sh("git", "-C", repo, "cat-file", "-e", f"{base}:{f}").returncode == 0]
for name, rev in (("base0", base), ("base", base), ("fix", merge)):
    d = f"{work}/{name}"
    tree(rev, d)
    if name == "base":
        for f in tests:                                  # the maintainers' version of each test file over the base tree
            c = sh("git", "-C", repo, "show", f"{merge}:{f}")
            if c.returncode == 0:
                os.makedirs(os.path.dirname(f"{d}/{f}"), exist_ok=True)
                open(f"{d}/{f}", "w").write(c.stdout)
            elif os.path.exists(f"{d}/{f}"):
                os.remove(f"{d}/{f}")
    # base0: the base with its own test files (only those that exist there): which test ids existed before the PR
    out[name], whys[name] = run(d, EXISTING) if name == "base0" and EXISTING else (run(d) if name != "base0" else ({}, {}))
b0, b, f = out["base0"], out["base"], out["fix"]
added = sorted(n for n in f if n not in b0)             # ids that exist only with the PR's tests
f2p_all = sorted(n for n, s in f.items() if s == "PASSED" and b.get(n) != "PASSED")
f2p = [n for n in f2p_all if n in set(added)]
p2p = sorted(n for n, s in f.items() if s == "PASSED" and b.get(n) == "PASSED")
# a name that does not exist at the base: the feature's API is absent (not a bug whose symptom is some other AttributeError)
MISSING_NAME = re.compile(r"cannot import name|No module named|ModuleNotFoundError|ImportError|module '[\w.]+' has no attribute|"
                          r"name '\w+' is not defined|\bis not defined\b")


def base_reason(n):
    w = whys["base"]
    if n in w:
        return w[n]
    mod = n.split("::")[0]
    if runner == "unittest":
        return next((v for k, v in w.items() if k.startswith("MODULE::") and (mod.startswith(k[8:]) or k[8:].startswith(mod))), None)
    return w.get(mod)                                    # pytest: a file that did not import is reported once for the file


reasons = {n: base_reason(n) for n in f2p}
api_absent = any(MISSING_NAME.search(str(r or "")) for r in reasons.values())   # one is enough: a PR may bundle other tests
fix_bad = [n for n, s in f.items() if s != "PASSED"]
valid = bool(f2p) and not fix_bad
print(json.dumps({"tests": tests, "base_ran": len(b), "fix_ran": len(f), "fix_not_passing": sorted(fix_bad)[:3],
                  "f2p": len(f2p_all), "f2p_added": len(f2p), "added": len(added), "p2p": len(p2p), "valid_v1": bool(f2p_all) and not fix_bad,
                  "valid": valid, "group": ("invalid" if not valid else "rubric_only" if api_absent else "tested"),
                  "base_reasons": sorted(set(str(r)[:90] for r in reasons.values())), "f2p_sample": f2p[:3]}))
