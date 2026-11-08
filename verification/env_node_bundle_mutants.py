"""Mutants for SPEC_PWA_VIEWER E2 (Tailwind in pwa_node22: a locked package bundled in a fetched one is accepted, nothing
else without a registry sha512): each alone; killed = a test failed. Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
B = "scripts/build_env_node.sh"
T = ["tests/test_env_node.py", "-k", "not image_passes and not two_builds"]
M = [
    ("bundled always accepted", B, '    if v.get("inBundle") is not True or "resolved" in v or "integrity" in v:\n        return False',
     '    if True:\n        return True'),
    ("bundled never accepted", B, "bad += [k for k, v in packages.items() if k and not (fetched(v) or bundled(k, v))]",
     "bad += [k for k, v in packages.items() if k and not fetched(v)]"),
    ("truthy inBundle", B, 'if v.get("inBundle") is not True or', 'if not v.get("inBundle") or'),
    ("own source allowed", B, 'if v.get("inBundle") is not True or "resolved" in v or "integrity" in v:',
     'if v.get("inBundle") is not True or "integrity" in v:'),
    ("own hash allowed", B, 'if v.get("inBundle") is not True or "resolved" in v or "integrity" in v:',
     'if v.get("inBundle") is not True or "resolved" in v:'),
    ("bundleDependencies not checked", B, ' and parts[i] in (parent.get("bundleDependencies") or [])', ""),
    ("parent not checked", B, "            return fetched(parent) and", "            return True and"),
    ("any ancestor, bundled too", B, '        if parent.get("inBundle") is not True:', "        if True:"),
    ("missing ancestor skipped", B, "        if parent is None:\n            return False", "        if parent is None:\n            continue"),
    ("orphan accepted", B, "bundleDependencies\") or [])\n    return False", "bundleDependencies\") or [])\n    return True"),
]
# Equivalent, not listed: starting the ancestor walk at the package itself (range(len(parts), ...)), which is inBundle and
# so skipped; a top-level bundled package is refused either way (tested).

if __name__ == "__main__":
    killed = 0
    for name, f, old, new in M:
        p = WT / f
        orig = p.read_text()
        assert orig.count(old) == 1, (name, orig.count(old))
        p.write_text(orig.replace(old, new, 1))
        try:
            r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *T], cwd=WT,
                               capture_output=True, text=True, timeout=300)
        finally:
            p.write_text(orig)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        k = r.returncode == 1 and "failed" in last          # a test failed (not a collection or internal error)
        killed += k
        print(f"{'KILLED ' if k else 'SURVIVED'} {name}: {last}", flush=True)
    print(f"RESULT: {killed}/{len(M)} killed")
