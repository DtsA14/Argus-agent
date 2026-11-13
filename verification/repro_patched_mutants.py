"""Mutants for SPEC_REPRO_PATCHED (the issue example run again on the patched tree, display only): each applied alone in a
worktree, tests/test_repro_patched.py runs with -x; killed = a test of that file FAILED and pytest reported no error (an
import or fixture error, or a skip, is not a kill). Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
J, R = "router/job.py", "acceptance/repro.py"
T = ["-rfEs", "tests/test_repro_patched.py"]
CALL = '    _repro_patched(job, sid, out, cfg, deps)      # after the state is saved: nothing here can hold the job\n'
MOVE = '    job.move(REVIEW_READY if out["valid"] else REVIEW_INVALID, deps, stage=sid)\n'
M = [
    # P2: when and on what
    ("run before REVIEW_READY is saved", J, [(MOVE + CALL, CALL + MOVE)]),
    ("run on the base tree, not the patched one", J, [('repro.run_patched(job.root / "fixtures" / "repos" / BASE, patch, issue, scfg)',
                                                        'repro.run(job.root / "fixtures" / "repos" / BASE, issue, scfg)')]),
    ("an invalid package is run too", J, [('        if not out["valid"]:\n            repro.store_patched', '        if False:\n            repro.store_patched')]),
    ("invalid package leaves no reason", J, [('repro.store_patched(path, issue, sha, skipped="review package invalid")',
                                              'repro.store_patched(path, issue, sha)')]),
    ("no marker before the run", J, [('        repro.store_patched(path, issue, sha)                    # the marker: a run cut off reads "not run (error)"\n', '')]),
    ("an error in the step reaches the job", J, [('    except Exception:\n        found = None\n    try:\n        job.note(deps, "repro_patched"',
                                                  '    except ZeroDivisionError:\n        found = None\n    try:\n        job.note(deps, "repro_patched"')]),
    ("the final write is not a replace", R, [("        os.replace(tmp, path)\n", "        path.write_bytes(tmp.read_bytes())\n")]),
    # P3: label, line, key
    ("label in one direction only", R, [('("unchanged" if kb == kp else "changed")', '("unchanged" if kb == kp or kp[0] == "raised" else "changed")')]),
    ("label swapped", R, [('("unchanged" if kb == kp else "changed")', '("changed" if kb == kp else "unchanged")')]),
    ("exception type not compared", R, [('exc = (r.get("stderr_last_line") or "").split(":", 1)[0].strip() if r["status"] == "raised" else ""', 'exc = ""')]),
    ("status shows the first stage's file", J, [("        sid, st = last_agent(job)\n        rv = (st or {}).get(\"review\")",
                                                  "        sid = agent_stages(job)[0]\n        st = job.data[\"stages\"][sid]\n        rv = (st or {}).get(\"review\")")]),
    ("key without the patch", R, [('f"patched\\n{patch_sha256}\\n{issue}"', 'f"patched\\n{issue}"')]),
    ("key without the issue", R, [('f"patched\\n{patch_sha256}\\n{issue}"', 'f"patched\\n{patch_sha256}"')]),
    ("stale never detected", R, [('        if rec.get("key") != pkey(issue, patch_sha256):', '        if False:')]),
    ("a job from before gets a line", R, [("    if state is None:\n        return None\n    kind, val = state", '    if state is None:\n        return PREFIX + "not run (error)"\n    kind, val = state')]),
    ("nothing-ran case still compared", R, [("    if not any(_kind(r) for r in val) and not any(_kind(r) for r in base or []):", "    if False:")]),
    ("output not cleaned on read", R, [('[{k: (_cut(r.get(k), MAX_OUT) if k in clean else r.get(k)) for k in KEEP}\n                            for r in rec["results"] if isinstance(r, dict)])\n    except Exception:\n        return ("error", None)',
                                         '[{k: r.get(k) for k in KEEP}\n                            for r in rec["results"] if isinstance(r, dict)])\n    except Exception:\n        return ("error", None)')]),
    ("old sentence", R, [('PATCHED_SENTENCE = "the example runs agent-written code; compare both outputs against the issue"',
                          'PATCHED_SENTENCE = "a clean run does not prove the bug is fixed"')]),
]

if __name__ == "__main__":
    killed = 0
    for name, f, edits in M:
        p = WT / f
        orig = p.read_text()
        text = orig
        for a, b in edits:
            assert text.count(a) == 1, (name, a[:50], text.count(a))
            text = text.replace(a, b, 1)
        p.write_text(text)
        try:
            r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *T], cwd=WT,
                               capture_output=True, text=True, timeout=1800)
        finally:
            p.write_text(orig)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        fails = [line for line in r.stdout.splitlines() if line.startswith("FAILED tests/test_repro_patched.py")][:1]
        k = bool(fails) and "error" not in last
        killed += k
        verdict = "KILLED " if k else "SKIPPED" if "skipped" in last else "ERROR  " if "error" in last else "SURVIVED"
        print(f"{verdict} {name}: {fails or last}", flush=True)
    print(f"RESULT: {killed}/{len(M)} killed")
