"""Mutants for the staging namespace fix and `argus stage restart` (Atha 2026-10-30): each applied alone in a worktree,
the named tests run with -x; killed = a test failed (an error or a skip is not a kill). Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
S = "router/stage.py"
T = ["tests/test_stage.py"]
M = [
    ("running() without the directory filter", S, ' "--filter",\n                                f"label={BASE_LABEL}={self.base_label}",', ",", T),
    ("remove() without the directory check", S, "        if owner != self.base_label:", "        if False:", T),
    ("remove() takes a daemon error for no container", S, '        if "no such" in (err or "").lower():',
     "        if True:", T),
    ("tests share the real prefix and label", S, "        self.prefix, self.label = prefix, label",
     "        self.prefix, self.label = PREFIX, LABEL", T),
    ("directory label not resolved", S, "        self.base_label = str(self.base.resolve())",
     "        self.base_label = str(self.base)", T),
    ("container started without its directory label", S, '"--label",\n            f"{BASE_LABEL}={self.base_label}", "--network"',
     '"--network"', T),
    ("isolation does not check the directory label", S,
     "        if (cfg.get(\"Labels\") or {}).get(BASE_LABEL) != self.base_label:", "        if False:", T),
    ("restart while its container exists", S, "        if st.owner(name) is not None:", "        if False:", T),
    ("restart on today's image", S, '        image = rec.get("image") or (V0_IMAGE if runtime == ENVIRONMENT else None)',
     "        image = runtime_image(None, runtime)", T),
    ("restart without a digest check", S,
     '        if not (isinstance(image, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", image)):', "        if False:", T),
    ("restart records a failed smoke test", S,
     '        if not ok:\n            stopped = st.discard(name, "restart smoke_failed")',
     '        if False:\n            stopped = st.discard(name, "restart smoke_failed")', T),
    ("restart reconciles", S, '        live = st.state()["live"]\n        if not live:\n            raise Refused("nothing is live: there',
     '        st.reconcile()\n        live = st.state()["live"]\n        if not live:\n            raise Refused("nothing is live: there', T),
    ("restart not confirmed", S, '                                   "staging only: no production, no users, no credentials"]))\n        st.start(live, image)',
     '                                   "staging only: no production, no users, no credentials"]) or True)\n        st.start(live, image)', T),
    ("restart of nothing live", S, '        if not live:\n            raise Refused("nothing is live: there', '        if False:\n            raise Refused("nothing is live: there', T),
]

if __name__ == "__main__":
    killed = 0
    for name, f, old, new, tests in M:
        p = WT / f
        orig = p.read_text()
        assert orig.count(old) == 1, (name, orig.count(old))
        p.write_text(orig.replace(old, new, 1))
        r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *tests], cwd=WT,
                           capture_output=True, text=True)
        p.write_text(orig)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        k = "failed" in last
        killed += k
        fails = [line for line in r.stdout.splitlines() if line.startswith("FAILED")][:1]
        print(f"{'KILLED ' if k else 'SURVIVED'} {name}: {fails or last}", flush=True)
    print(f"RESULT: {killed}/{len(M)} killed")
