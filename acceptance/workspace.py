"""The task's workspace: a copy of the input repository in the run directory, its snapshot, and the scope check.

The agent only ever works in the copy. What changed is decided by comparing snapshots (path -> sha256) taken by the
harness, never by what the agent says it changed. Anything that is not a regular file or a directory (a symlink,
a FIFO, a device) is itself a violation: the path jail refuses symlinks, and the snapshot must not follow them.
"""
import hashlib
import os
import shutil
import stat
from pathlib import Path

from .contract import SUMMARY, matches

SPECIAL = "<not a regular file>"
CACHE = "__pycache__"           # bytecode caches of the input checkout are never part of the task


def snapshot(root, skip_cache=False):
    """{relative posix path: sha256 hex, or SPECIAL} for everything below root. Directories are walked without
    following symlinks; empty directories are not recorded (they cannot carry code)."""
    root = Path(root)
    out = {}
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        here = Path(dirpath)
        for name in list(dirnames):
            p = here / name
            if skip_cache and name == CACHE:
                dirnames.remove(name)
                continue
            if p.is_symlink():                       # os.walk lists symlinked dirs here; never enter them
                out[p.relative_to(root).as_posix()] = SPECIAL
                dirnames.remove(name)
        for name in filenames:
            p = here / name
            rel = p.relative_to(root).as_posix()
            st = os.lstat(p)
            if not stat.S_ISREG(st.st_mode):
                out[rel] = SPECIAL
                continue
            h = hashlib.sha256()
            with open(p, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 16), b""):
                    h.update(chunk)
            out[rel] = h.hexdigest()
    return out


def digest(snap):
    """One hash for a whole snapshot: a verdict is only valid for the exact workspace it was reached on."""
    h = hashlib.sha256()
    for k in sorted(snap):
        h.update(f"{k}\0{snap[k]}\n".encode("utf-8"))
    return h.hexdigest()


def prepare(src, dest):
    """Copy the input repository to dest (which must not exist) and return its snapshot. The input must be plain
    files and directories only."""
    src, dest = Path(src), Path(dest)
    before = snapshot(src, skip_cache=True)
    bad = [p for p, h in before.items() if h == SPECIAL]
    if bad:
        raise ValueError(f"input repository has entries that are not regular files: {bad}")
    shutil.copytree(src, dest, symlinks=True, ignore=shutil.ignore_patterns(CACHE))
    copied = snapshot(dest)
    if copied != before:
        raise RuntimeError("workspace copy differs from the input repository")
    return copied


def diff(before, after):
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    modified = sorted(p for p in set(before) & set(after) if before[p] != after[p])
    return {"added": added, "removed": removed, "modified": modified}


def scope_check(contract, before, after):
    """Criterion verdicts for layer A (scope): protected files untouched, changes only where writable, and no
    special files. The SUMMARY.json artifact is the one path outside the scope globs that the agent may write."""
    d = diff(before, after)
    sc = contract["scope"]
    changed = d["added"] + d["removed"] + d["modified"]
    protected = [p for p in changed if matches(p, sc["protected"])]
    outside = [p for p in changed if p != SUMMARY and not matches(p, sc["protected"])
               and not matches(p, sc["writable"])]
    special = sorted(p for p, h in after.items() if h == SPECIAL)
    ev = {"diff": d}
    return [
        {"id": "scope:protected", "layer": "A", "status": "fail" if protected else "pass",
         "reason": f"protected files changed: {protected}" if protected else "", "evidence": ev},
        {"id": "scope:writable", "layer": "A", "status": "fail" if outside else "pass",
         "reason": f"files changed outside the writable scope: {outside}" if outside else "", "evidence": ev},
        {"id": "scope:regular_files", "layer": "A", "status": "fail" if special else "pass",
         "reason": f"entries that are not regular files: {special}" if special else "", "evidence": {}},
    ]
