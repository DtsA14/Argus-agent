#!/usr/bin/env python3
"""Recompute the two pins a chat change usually breaks: `STATIC_SHA256` (router/chat.py: index.html, app.js, app.css) and `SHEET_SHA256`
(router/manager_route.py: docs/CHAT_CAPABILITIES.md). It does not review anything: the pin is a barrier against an UNREVIEWED edit, and this only
follows an edit that went through the lane. Run it as the last step of a change, then commit the two lines it changed.
`SW_SHA256` of the viewer is NOT touched (a reviewed file from another skeleton; changing it is its own strict change).

Usage: scripts/repin.py            rewrite the stale pins, print what changed
       scripts/repin.py --check    print the stale pins and exit 1 if there are any; writes nothing
       scripts/repin.py --root DIR use another checkout (the tests do)"""
import argparse
import hashlib
import re
import sys
from pathlib import Path

STATIC = ("index.html", "app.js", "app.css")


def computed(root):
    out = {}
    for n in STATIC:
        out[("router/chat.py", n)] = hashlib.sha256((root / "router" / "chat_static" / n).read_bytes()).hexdigest()
    out[("router/manager_route.py", "SHEET_SHA256")] = hashlib.sha256((root / "docs" / "CHAT_CAPABILITIES.md").read_text(encoding="utf-8").encode("utf-8")).hexdigest()
    return out


def pattern(f, key):
    return re.compile(r'(%s)' % (r'"%s": "' % re.escape(key) if f == "router/chat.py" else r'^%s = "' % re.escape(key)) + r'([0-9a-f]{64})', re.M)


def run(root, write):
    stale = []
    texts = {}
    for (f, key), new in computed(root).items():
        text = texts.setdefault(f, (root / f).read_text())
        pat = pattern(f, key)
        found = pat.findall(text)
        if len(found) != 1:
            raise SystemExit(f"repin: {key} appears {len(found)} times in {f} (expected once); nothing was written")
        if found[0][1] != new:
            stale.append((f, key, found[0][1][:12], new[:12]))
            texts[f] = pat.sub(lambda m: m.group(1) + new, text, count=1)
    if write:
        for f, text in texts.items():
            (root / f).write_text(text)
    return stale


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    o = ap.parse_args(argv)
    stale = run(Path(o.root), write=not o.check)
    for f, key, old, new in stale:
        print(f"{'stale' if o.check else 'repinned'}: {f} {key} {old} -> {new}")
    if not stale:
        print("repin: all pins match")
    return 1 if (stale and o.check) else 0


if __name__ == "__main__":
    sys.exit(main())
