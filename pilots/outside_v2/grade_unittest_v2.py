"""Batch 3 variant of outside_v1/grade_unittest.py: F2P counts only tests ADDED by the PR (ids absent when the base's own test files run on the base: validity rule v2).
One-off hidden-test grading (outside experiment). No model. Maintainer code runs only in the Docker sandbox.
usage: grade.py <id> <repo-dir> <parent> <merge> <patch>   -> prints per-node results as JSON"""
import json, os, re, shutil, subprocess, sys, tempfile
ident, repo, parent, merge, patch = sys.argv[1:6]
repo = os.path.expanduser(repo)
IMG = "sha256:3e48cd98c8de"
def sh(*a, **k): return subprocess.run(a, capture_output=True, text=True, **k)
def tree(rev, dest):
    os.makedirs(dest)
    p = subprocess.run(["git", "-C", repo, "archive", rev], capture_output=True, check=True)
    subprocess.run(["tar", "-x", "-C", dest], input=p.stdout, check=True)
changed = sh("git", "-C", repo, "diff", "--name-only", parent, merge).stdout.split()
tests = [f for f in changed if re.match(r"(tests?/|.*/tests?/)", f) and f.endswith(".py")]
if os.environ.get("GRADE_FILES"):
    tests = os.environ["GRADE_FILES"].split(",")          # only the test files of the fix PR itself
NAMES = set(os.environ.get("GRADE_NAMES", "").split(",")) - {""}
def run(root, files):
    mods = [f[:-3].replace("/", ".") for f in files]
    r = sh("docker", "run", "--rm", "--network", "none", "--read-only", "--cap-drop", "ALL", "--user", "65534:65534",
           "--memory", "512m", "--cpus", "1", "--pids-limit", "128", "--tmpfs", "/tmp:rw,size=64m,mode=1777",
           "-v", f"{root}:/workspace:ro", "-w", "/workspace", "-e", "PYTHONDONTWRITEBYTECODE=1", "-e", "PYTHONPATH=/workspace", IMG,
           "python3", "-B", "-m", "unittest", "-v", *mods, timeout=900)
    txt = r.stdout + r.stderr
    allt = set(re.findall(r"^(test\w*) \(([\w.]+)\)", txt, re.M))
    failed = {(m.group(1), m.group(2)) for m in re.finditer(r"^(?:FAIL|ERROR): (test\w*) \(([\w.]+)\)", txt, re.M)}
    res = {c + "::" + n: ("FAILED" if (n, c) in failed else "PASSED") for n, c in allt | failed}
    return res, txt[-400:]
out = {"id": ident, "test_files": tests}
work = tempfile.mkdtemp(prefix="grade_")   # outside any git repo: git apply from a subfolder of a repo silently skips paths outside it
def variant(name, base_rev, patch_file=None, overlay=True):
    d = f"{work}/{name}"; tree(base_rev, d)
    if patch_file:
        txt = open(patch_file).read()
        txt = re.sub(r"^(old|new) mode \d+\n", "", txt, flags=re.M)
        pf = f"{work}/{name}.patch"; open(pf, "w").write(txt)
        a = sh("git", "apply", "--whitespace=nowarn", pf, cwd=d)
        if a.returncode: return None, "APPLY FAILED: " + a.stderr[:300]
    if overlay:
        for f in tests:
            c = sh("git", "-C", repo, "show", f"{merge}:{f}")
            if c.returncode == 0:
                os.makedirs(os.path.dirname(f"{d}/{f}"), exist_ok=True); open(f"{d}/{f}", "w").write(c.stdout)
            elif os.path.exists(f"{d}/{f}"): os.remove(f"{d}/{f}")
    return run(d, [f for f in tests if os.path.exists(f"{d}/{f}")])
out["base"] = variant("base", parent)
out["base0"] = variant("base0", parent, overlay=False)     # the base's own tests on the base: which ids already exist
out["fix"] = variant("fix", merge, overlay=True)
out["argus"] = variant("argus", parent, patch_file=patch)
json.dump(out, open(f"{work}/result.json", "w"), indent=1)
b, f, a = (out[k][0] for k in ("base", "fix", "argus"))
print(ident, "test files:", tests, "| work:", work)
if not f: print("FIX variant failed:", out["fix"][1]); sys.exit(0)
if not a: print("ARGUS variant:", out["argus"][1]); sys.exit(0)
B0 = set((out["base0"][0] or {}))
f2p = sorted(n for n, s in f.items() if s == "PASSED" and b.get(n) != "PASSED" and n not in B0)
f2p_old = sorted(n for n, s in f.items() if s == "PASSED" and b.get(n) != "PASSED" and n in B0)   # changed old tests: reported, not counted
p2p = sorted(n for n, s in f.items() if s == "PASSED" and b.get(n) == "PASSED")
bad_fix = sorted(n for n, s in f.items() if s != "PASSED")
print(f"fix: {sum(s=='PASSED' for s in f.values())}/{len(f)} pass (non-pass: {bad_fix[:5]})")
print(f"FAIL_TO_PASS (added) {len(f2p)}, PASS_TO_PASS {len(p2p)}; changed old tests failing at base: {len(f2p_old)}")
af = [n for n in f2p if a.get(n) != "PASSED"]; ap = [n for n in p2p if a.get(n) != "PASSED"]
print(f"argus F2P failing {len(af)}/{len(f2p)}: {af[:6]}")
print(f"argus P2P failing {len(ap)}/{len(p2p)}: {ap[:6]}")
print("RESOLVED" if not af and not ap and not bad_fix else "NOT RESOLVED (read it)")
