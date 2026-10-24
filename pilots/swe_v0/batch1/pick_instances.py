"""Pick small SWE-bench Verified sympy instances: one file changed, few lines, 1-3 FAIL_TO_PASS."""
import json, re, sys
import pyarrow.parquet as pq
rows = pq.read_table(sys.argv[1]).to_pylist()
print("instances", len(rows), "columns", sorted(rows[0]))
sym = [r for r in rows if r["repo"] == "sympy/sympy"]
print("sympy", len(sym))
out = []
for r in sym:
    files = re.findall(r"^diff --git a/(\S+)", r["patch"], re.M)
    changed = sum(1 for l in r["patch"].splitlines() if l[:1] in "+-" and not l.startswith(("+++", "---")))
    f2p, p2p = json.loads(r["FAIL_TO_PASS"]), json.loads(r["PASS_TO_PASS"])
    tfiles = re.findall(r"^diff --git a/(\S+)", r["test_patch"], re.M)
    if len(files) == 1 and changed <= 12 and 1 <= len(f2p) <= 3 and len(tfiles) == 1:
        out.append((changed, r["instance_id"], r["version"], r["difficulty"], files[0], tfiles[0], len(f2p), len(p2p), r["created_at"][:10]))
for o in sorted(out):
    print(o)
