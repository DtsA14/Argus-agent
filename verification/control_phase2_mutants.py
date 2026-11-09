"""Mutants for the phone's control service, phase 2 (docs/reviews/SPEC_CONTROL_UI.md 4a, F9): each gate broken
alone; killed = a test failed. Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
C, J = "router/control.py", "router/job.py"
T = ["tests/test_control.py"]
M = [
    ("bind anywhere", C, 'BIND, PORT = "127.0.0.1", 8711', 'BIND, PORT = "0.0.0.0", 8711'),
    ("no host check", C, '        if self.headers.get("Host") in HOSTS:\n            return True', '        if True:\n            return True'),
    ("no origin check", C, '        if origin not in ORIGINS:\n', '        if False:\n'),
    ("missing origin allowed", C, '        if origin not in ORIGINS:', '        if origin is not None and origin not in ORIGINS:'),
    ("sec-fetch-site ignored", C, 'if headers.get("Sec-Fetch-Site") not in (None, "same-origin"):', 'if False:'),
    ("token mac unchecked", C, '        if not hmac.compare_digest(mac, self._mac(action, job, sha, int(issued))):', '        if False:'),
    ("token never expires", C, '        if not 0 <= now - int(issued) <= TOKEN_TTL:', '        if False:'),
    ("token reusable", C, '        if token in self.used:', '        if False:'),
    ("token not bound to action", C, 'f"{action}|{job}|{sha}|{issued}"', 'f"{job}|{sha}|{issued}"'),
    ("token not bound to sha", C, 'f"{action}|{job}|{sha}|{issued}"', 'f"{action}|{job}|{issued}"'),
    ("reason not required", C, 'why = reason_problem(reason, required=action == "reject")', 'why = reason_problem(reason, required=False)'),
    ("reason length", C, '    if len(reason) > REASON_MAX:', '    if False:'),
    ("control characters", C, '    if any(ord(c) < 32 or 127 <= ord(c) < 160 for c in reason):', '    if False:'),
    ("full strip", C, 'reason = reason.strip(" ")', 'reason = reason.strip()'),
    ("any id", C, '        if not UI_ID.match(job_id or ""):\n            return None', '        if not job_id:\n            return None'),
    ("sha not passed", C, '*(["--sha", sha] if sha else [])', '*([])'),
    ("no -- separator", C, ', "--", job_id, reason]', ', job_id, reason]'),
    ("no body limit", C, 'if 0 <= length <= BODY_MAX else None', 'if 0 <= length else None'),
    ("no security headers", C, '        for k, v in HEADERS.items():\n            self.send_header(k, v)\n', ''),
    ("state not escaped", C, '<p>{e(state)}</p>', '<p>{state}</p>'),
    ("duplicate fields", C, 'if len(form.get(k) or [""]) == 1 else None', 'if True else None'),
    ("no audit of a refusal", C, '            self.audit(**rec, refused=gate, why=why)\n', ''),
    ("draft sha unchecked", J, '        if not seen.startswith(sha):', '        if False:'),
    ("via unchecked", J, '        if via not in VIA:', '        if False:'),
    ("sha without draft accepted", J, '            raise Refused(f"job {job.id} has no draft to check the sha {sha} against; nothing was changed") from None', '            return {"sha": sha}'),
]
# Equivalent, not listed: dropping the 12-hex shape check of the form's sha. The token is bound to the sha the server
# put in the page (its own sha12 or ""), so a sha of another shape never passes the token gate before it.

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
