"""Mutants for SPEC_PATCH_READER_SEVERITY: each applied alone in a worktree; killed = a test FAILED and pytest reported no error.
Usage: <this> <worktree> <python> [name fragments]."""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
ONLY = sys.argv[3:]
PT, PR, PA, PQ, PRR, AC, JB = ("router/patch_trial.py", "router/patch_read.py", "router/apply.py", "router/queue.py", "router/patch_read_run.py",
                               "router/approve_code.py", "router/job.py")
T = ["-rfEs", "tests/test_patch_read_severity.py", "tests/test_patch_trial.py", "tests/test_patch_read_run.py", "tests/test_patch_read.py", "tests/test_queue.py",
     "tests/test_approve_code.py", "tests/test_apply_cmd.py"]
M = [
    ("parse ignores a disagreeing severity", PT, [("len({(v, sv) for v, _, sv in found}) != 1", "len({v for v, _, sv in found}) != 1")]),
    ("parse: an absent severity is a nit", PT, [('"nit" if d.get("severity") == "nit" else "blocker"', '"blocker" if d.get("severity") == "blocker" else "nit"')]),
    ("parse keeps a severity on an ok", PT, [('sev = None if d["verdict"] == "ok" else "nit"', 'sev = "nit"')]),
    ("the trial does not count defect nits", PT, [('def_nits += used.count("nit")', "def_nits += 0")]),
    ("a pair run with a nit and a blocker is a nit", PT, [('"blocker" if "blocker" in sevs else "nit"', '"nit" if "nit" in sevs else "blocker"')]),
    ("the trial reads an absent severity as a nit", PT, [('r.get("severity", "blocker")', 'r.get("severity", "nit")')]),
    ("the trial does not write the severity", PT, [('**({"severity": got[2]} if got[2] else {}), ', "")]),
    ("the second record drops the first severity", PR, [('"template_sha256", "severity") if k in old}', '"template_sha256") if k in old}')]),
    ("an ok stores a severity", PR, [('**({"severity": "nit" if severity == "nit" else "blocker"} if verdict == "concerns" else {})', '**({"severity": "nit" if severity == "nit" else "blocker"})')]),
    ("a nit pair is written over", PR, [('if kind0 in ("concerns", "nit") and not (second', 'if kind0 == "concerns" and not (second')]),
    ("an unknown severity is valid", PR, [('return "severity" not in r or r["severity"] in SEVERITIES', "return True")]),
    ("a severity on an ok is valid", PR, [('    return "severity" not in r\n\n\ndef _pair_kind', "    return True\n\n\ndef _pair_kind")]),
    ("an absent severity is a nit", PR, [('return "nit" if r.get("severity") == "nit" else "blocker"', 'return "blocker" if r.get("severity") == "blocker" else "nit"')]),
    ("one nit among blockers is enough", PR, [('all(_sev(r) == "nit" for r in cons)', 'any(_sev(r) == "nit" for r in cons)')]),
    ("a Claude reading can make a nit pair", PR, [('if a.get("kind") != "argus" or b.get("kind") != "argus" or {', "if {")]),
    ("any two ids make a nit pair", PR, [('{a.get("id"), b.get("id")} != {prr.reader_id(prr.FIRST), prr.reader_id(prr.SECOND)} or a.get("id") == b.get("id")', 'a.get("id") == b.get("id")')]),
    ("a stale or damaged-template second is accepted in a nit pair", PR, [("if not (isinstance(sec, dict) and _second_ok(sec) and not _model_stale(sec) and not _model_stale(first)):", "if not (isinstance(sec, dict) and _second_ok(sec)):")]),
    ("a damaged second is accepted in a nit pair", PR, [("if not (isinstance(sec, dict) and _second_ok(sec) and not _model_stale(sec) and not _model_stale(first)):", "if not (isinstance(sec, dict) and not _model_stale(sec) and not _model_stale(first)):")]),
    ("a first nit alone is a nit", PR, [("return _pair_kind(rec, sec), rec", 'return "nit", rec')]),
    ("the merged record drops the second severity", PR, [('"at": sec["at"], "severity": _sev(sec)}', '"at": sec["at"]}')]),
    ("a second nit skips the pair check", PR, [('if _sev(sec) == "nit" and _pair_kind(rec, sec) == "nit":', 'if _sev(sec) == "nit":')]),
    ("--accept-concerns accepts a nit pair", PR, [('if kind in ("ok", "nit"):', 'if kind == "ok":')]),
    ("blockers_only keeps the nits", PR, [('not (blockers_only and _sev(r) == "nit")', "True")]),
    ("the template loses its blocker default", PR, [('When unsure: "blocker".', "")]),
    ("the nits are not logged by apply", PA, [('extra = {**extra, "accepted_nits": [list(f) for f in nits]}', "pass")]),
    ("a retry hands over the nits", PQ, [("pr.findings(rec, blockers_only=True)", "pr.findings(rec)")]),
    ("a nit pair is read again", PRR, [('if kind0 in ("ok", "nit") or', 'if kind0 == "ok" or')]),
    ("the run does not pass the severity to record", PRR, [("second=(n == 1), severity=severity)", "second=(n == 1))")]),
    ("the card stays closed on a nit pair", AC, [('_chk("f", pr_kind in ("ok", "nit"), {', '_chk("f", pr_kind == "ok", {')]),
    ("the card hides a nit pair", AC, [('if pr_kind in ("ok", "concerns", "nit") and pr_rec:', 'if pr_kind in ("ok", "concerns") and pr_rec:')]),
    ("the status prints no nit line", JB, [('        if kind == "nit":\n            read_line = (', '        if False:\n            read_line = (')]),
]

if __name__ == "__main__":
    killed = ran = 0
    for name, F, edits in M:
        if ONLY and not any(o in name for o in ONLY):
            continue
        p = WT / F
        orig = p.read_text()
        text = orig
        stale = [a[:70] for a, _ in edits if text.count(a) != 1]
        if stale:
            print(f"STALE   {name}: {stale}", flush=True)
            continue
        for a, b in edits:
            text = text.replace(a, b, 1)
        p.write_text(text)
        ran += 1
        try:
            r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", "-n", "4", *T], cwd=WT, capture_output=True, text=True, timeout=1800)
        finally:
            p.write_text(orig)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        fails = [line for line in r.stdout.splitlines() if line.startswith("FAILED tests/test_")][:1]
        k = bool(fails) and "error" not in last
        killed += k
        print(f"{'KILLED ' if k else 'ERROR  ' if 'error' in last else 'SURVIVED'} {name}: {fails or last}", flush=True)
    print(f"RESULT: {killed}/{ran} killed")
