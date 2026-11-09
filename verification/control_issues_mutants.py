"""Mutants for the issue writer's control pages (SPEC_ISSUE_WRITER 6, router/control_issues.py): each guarantee broken
alone; killed = a test failed. Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
C, R = "router/control_issues.py", "router/control.py"
T = ["tests/test_control_issues.py"]
M = [
    ("no origin check", C, "        why = c.origin_problem(headers)\n        if why:", "        why = None\n        if why:"),
    ("token never spent", C, '        why = c.tokens.spend(values["token"], f"issue-{action}", job.id if job else "", sha_now)',
     "        why = None"),
    ("token for any action", C, '        why = c.tokens.spend(values["token"], f"issue-{action}", job.id if job else "", sha_now)',
     '        why = c.tokens.spend(values["token"], "issue-reply" if action != "new" else "issue-new", '
     'job.id if job else "", sha_now)'),
    ("form token for any action", C, '        token = self.control.tokens.issue(f"issue-{action}", job.id, sha)',
     '        token = self.control.tokens.issue("issue-reply", job.id, sha)'),
    ("issue seen unchecked", C, '        if job is not None and values["sha"] != sha_now[:12]:          # before the token',
     "        if False:          # before the token"),
    ("any repository", C, '        if action == "new" and repo not in self.repos():', "        if False:"),
    ("message unchecked", C, '            why = ri.message_problem(self.cfg, text, first=action == "new")', "            why = None"),
    ("token before the form", C, '        if why:\n            return refuse(400, "form", why, job, text, repo)\n'
     '        sha_now = (job.data.get("issue_sha256") or "") if job is not None else ""\n',
     '        sha_now = (job.data.get("issue_sha256") or "") if job is not None else ""\n'
     '        why = c.tokens.spend(values["token"], f"issue-{action}", job.id if job else "", sha_now) or why\n'
     '        if why:\n            return refuse(400, "form", why, job, text, repo)\n'),
    ("CRLF kept", C, '    return text.replace("\\r\\n", "\\n").replace("\\r", "\\n").strip()', "    return text.strip()"),
    ("message in argv", C, '"--job-id", new_id, "--message-file", str(message))', '"--job-id", new_id, "--message", text)'),
    ("key file anyway", C, "        k = self.environ.get(KEY_ENV)\n        return k if k else None",
     '        k = self.environ.get(KEY_ENV)\n        return k if k else "/tmp/key"'),
    ("a second run", C, "        if self.spawner.busy(new_id):", "        if False:"),
    ("no separator", C, '"--message-file", str(message)) + ["--", job.id]', '"--message-file", str(message)) + [job.id]'),
    ("small body for messages", R, "limit = issues.body_max() if issue and issues else BODY_MAX", "limit = BODY_MAX"),
    ("any body limit", C, "        return v if isinstance(v, int) and not isinstance(v, bool) and v > BODY_MAX else BODY_MAX",
     "        return v"),
    ("text not escaped", C, '<p class="text">{E(m["text"])}</p>', '<p class="text">{m["text"]}</p>'),
    ("no reload while busy", C, "        return self._page(job.id, \"\".join(parts), refresh=REFRESH_S if working else None)",
     '        return self._page(job.id, "".join(parts), refresh=None)'),
    ("forms while busy", C, "        if not busy:\n            if self.key_file() is None and state in ri.REPLYABLE:",
     "        if True:\n            if self.key_file() is None and state in ri.REPLYABLE:"),
    ("message file readable", C, "os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)", "os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)"),
    ("message file kept", C, '            if run["message"] is not None:\n                Path(run["message"]).unlink(missing_ok=True)\n', ""),
    ("refused text not kept", C, '"text": run["text"] if code not in (0, 1) else None}', '"text": None}'),
    ("outcome not shown", C, '        elif out is not None and out["code"] not in (0, 1):', "        elif False:"),
    ("no pending page", R, "            if pending is not None:                # a new job", "            if False:                # a new job"),
    ("stale files kept", C, "                if self.clock() - f.stat().st_mtime > self.STALE_S:\n                    f.unlink()",
     "                if False:\n                    f.unlink()"),
    ("index reads every job", C, "(sorted(d.iterdir(), reverse=True) if d.is_dir() else [])[:INDEX_MAX]",
     "(sorted(d.iterdir(), reverse=True) if d.is_dir() else [])"),
    ("discard beside a cut-off start", C, '            if d.get("handoff") and state == ri.AWAITING_HUMAN:', "            if False:"),
    ("abandon orphans a code job", "router/job.py", "            if code is not None:        # a cut-off start", "            if False:        # a cut-off start"),
    ("refused twice", C, "f\"refused: {strip_refused(line) or 'the command failed'}\"", "f\"refused: {line or 'the command failed'}\""),
    ("any kind", C, '        return job if job is not None and job.data.get("kind") == "issue" else None', "        return job"),
    ("no attempt line", C, '        c.audit(**rec, attempt=action, sha=values.get("sha") or None)\n', ""),
    ("abandon reason unchecked", C, '            why = reason_problem(values["reason"], required=False)', "            why = None"),
    ("job id from the form", C, '        new_id = rj.new_job_id() if action == "new" else job.id', '        new_id = rj.new_job_id()'),
]

if __name__ == "__main__":
    killed = 0
    for name, f, old, new in M:
        p = WT / f
        orig = p.read_text()
        assert orig.count(old) == 1, (name, orig.count(old))
        p.write_text(orig.replace(old, new, 1))
        try:
            r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *T], cwd=WT,
                               capture_output=True, text=True, timeout=600)
        finally:
            p.write_text(orig)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        k = r.returncode == 1 and "failed" in last          # a test failed (not a collection or internal error)
        killed += k
        print(f"{'KILLED ' if k else 'SURVIVED'} {name}: {last}", flush=True)
    print(f"RESULT: {killed}/{len(M)} killed")
