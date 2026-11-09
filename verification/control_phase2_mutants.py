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
    ("token reusable", C, '        if mac in self.used:', '        if False:'),
    ("token not bound to action", C, 'f"{action}|{job}|{sha}|{issued}"', 'f"{job}|{sha}|{issued}"'),
    ("token not bound to sha", C, 'f"{action}|{job}|{sha}|{issued}"', 'f"{action}|{job}|{issued}"'),
    ("reason not required", C, 'why = reason_problem(reason, required=action == "reject")', 'why = reason_problem(reason, required=False)'),
    ("reason length", C, '    if len(reason) > REASON_MAX:', '    if False:'),
    ("control characters", C, 'unicodedata.category(c)[0] == "C" or ', ''),
    ("line separators", C, ' or unicodedata.category(c) in ("Zl", "Zp")', ''),
    ("full strip", C, 'reason = reason.strip(" ")', 'reason = reason.strip()'),
    ("any id", C, '        if not UI_ID.fullmatch(job_id or ""):\n            return None', '        if not job_id:\n            return None'),
    ("id prefix only", C, '        if not UI_ID.fullmatch(job_id or ""):', '        if not UI_ID.match(job_id or ""):'),
    ("too many fields unaudited", C, '            return refuse(400, "form", "too many fields", job)', '            raise'),
    ("sha not passed", C, '*(["--sha", sha] if sha else [])', '*([])'),
    ("no -- separator", C, ', "--", job_id, reason]', ', job_id, reason]'),
    ("no body limit", C, 'if 0 <= length <= BODY_MAX else None', 'if 0 <= length else None'),
    ("no-referrer again", C, '"Referrer-Policy": "same-origin"', '"Referrer-Policy": "no-referrer"'),
    ("origin not audited", C, '            rec["origin"] = (origin or "")[:100] if origin is not None else None\n', ''),
    ("no security headers", C, '        for k, v in HEADERS.items():\n            self.send_header(k, v)\n', ''),
    ("state not escaped", C, '<p>{e(state)}</p>', '<p>{state}</p>'),
    ("duplicate fields", C, 'if len(form.get(k) or [""]) == 1 else None', 'if True else None'),
    ("no audit of a refusal", C, '            self.audit(**rec, refused=gate, why=why)\n', ''),
    ("page before the draft", C, '        if sha != current:', '        if sha and sha != current:'),
    ("unreadable is no draft", C, '        raise Unreadable(f"the draft cannot be read: {type(e).__name__}") from None', '        return None'),
    ("no attempt line", C, '        self.audit(**rec, attempt=action, sha=sha or None)          # before the job changes (F5)\n', ''),
    ("token spent before the form", C, '        if why:\n            return refuse(400, "form", why, job, reason)\n        why = self.tokens.spend(token, action, job.id, sha)', '        why = self.tokens.spend(token, action, job.id, sha) or why'),
    ("reason not written back", C, 'value="{e(reason)}" ', ''),
    ("doubled prefix", C, '        line = line[len("refused: "):] if line.startswith("refused: ") else line\n', ''),
    ("no client timeout", C, '    timeout = 10 ', '    timeout = None '),
    ("sha with a newline", J, '        if not SHA_SEEN.fullmatch(sha):', '        if not re.match(r"^[0-9a-f]{12,64}$", sha):'),
    ("draft sha unchecked", J, '        if not seen.startswith(sha):', '        if False:'),
    ("via unchecked", J, '        if via not in VIA:', '        if False:'),
    ("sha without draft accepted", J, '            raise Refused(f"job {job.id} has no draft to check the sha {sha} against; nothing was changed") from None', '            return {"sha": sha}'),
]
# Equivalent, not listed: dropping the 12-hex shape check of the form's sha. The token is bound to the sha the server
# put in the page (its own sha12 or ""), so a sha of another shape never passes the token gate before it. Also `\\d` for
# [0-9] in UI_ID: a segment with other Unicode digits is refused by rj.JOB_ID (ASCII) in open_job anyway. And the
# one-spelling rule of a token's issue time: the spent set is keyed on the mac, which another spelling of the same
# time does not change, so the replay is refused as "already sent" either way (tested).

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
