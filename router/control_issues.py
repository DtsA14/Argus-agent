"""The issue writer's pages of the control service (docs/reviews/SPEC_ISSUE_WRITER.md section 6): a conversation
with the writer from the phone, then Start job.

  GET  /issues                    the issue jobs, newest first, and New issue
  GET  /issues/new                a repository of issue_writer.repos and the first message
  GET  /issues/<id>               the conversation, the current issue (folded), its clashes and questions, the forms
  POST /issues/new                `argus issue new` in the background, then the job's page
  POST /issues/<id>/reply         `argus issue reply` in the background
  POST /issues/<id>/start         `argus issue start --sha` in the background (the code job's drafter runs)
  POST /issues/<id>/abandon       `argus abandon`, at once

Every POST passes the gates of router/control.py (Host, Origin and Sec-Fetch-Site, the form before the token, a
one-time token bound to the action, the job and its issue's sha), then runs the same CLI a human types: the job's lock,
its states, the funding and the sha checks stay in router/issue.py. A message goes to the CLI in a file the service
writes (never in argv). The CLI gets --key-file from the service's environment (ARGUS_CONTROL_KEY_FILE, set by Atha);
the service never reads a key. Runs that take minutes (a writer's turn, a drafter) are child processes in their own
session; a page shows that the job is busy and reloads itself every few seconds (no JavaScript).
"""
import calendar
import html
import json
import os
import re
import secrets
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs

from router import issue as ri
from router import job as rj
from router.control import strip_refused

KEY_ENV = "ARGUS_CONTROL_KEY_FILE"
STATE = Path.home() / ".local" / "state" / "argus-control"
REFRESH_S = 3
STEPS_SHOWN = 12                # the last writer steps a page shows while a turn runs (amendment 1, A2)
EVENTS_TAIL = 64 * 1024         # the bytes of the turn's events.jsonl a page reads
DOING = {"ReadFile": "Reading", "SearchFiles": "Searching", "ListFiles": "Listing files", "SubmitIssue": "Writing"}
ISSUE_ACTIONS = ("reply", "start", "abandon")
INDEX_MAX = 200                 # the newest job directories /issues reads (job ids sort by time)
FIELDS = {"new": ("token", "repo", "message"), "reply": ("token", "sha", "message"), "start": ("token", "sha"),
          "abandon": ("token", "sha", "reason")}
E = html.escape


def normalize(text):
    """A browser's textarea sends CRLF line ends: one `\\n` each, so the CLI's rules see the text as typed."""
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


class Spawner:
    """The background runs, one per job at a time: a child process in its own session, its output in a log file of the
    service's state directory. Every finished run is reaped at the next request (its message file removed), and its
    outcome kept until the job's next run: the exit code, the last line it printed, and the human's text when it was
    refused, so the page can say why and give the text back. Message files a restart left behind are removed."""

    STALE_S = 600

    def __init__(self, state=STATE, clock=time.time):
        self.state, self.clock = Path(state), clock
        self.runs, self.ended = {}, {}             # job id -> the run in progress / the last run's outcome
        for f in (self.state / "messages").glob("*.txt") if (self.state / "messages").is_dir() else []:
            try:
                if self.clock() - f.stat().st_mtime > self.STALE_S:
                    f.unlink()
            except OSError:
                pass

    def reap(self):
        for job_id, run in list(self.runs.items()):
            code = run["popen"].poll()
            if code is None:
                continue
            line = last_line(run["log"])
            self.ended[job_id] = {"code": code, "line": line, "action": run["action"],
                                  "text": run["text"] if code not in (0, 1) else None}
            if run["message"] is not None:
                Path(run["message"]).unlink(missing_ok=True)
            del self.runs[job_id]

    def busy(self, job_id):
        self.reap()
        return job_id in self.runs

    def outcome(self, job_id):
        self.reap()
        return None if job_id in self.runs else self.ended.get(job_id)

    def message_file(self, text):
        d = self.state / "messages"
        d.mkdir(parents=True, exist_ok=True)
        p = d / f"{secrets.token_hex(8)}.txt"
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        return p

    def spawn(self, job_id, argv, message=None, action="", text=None):
        logs = self.state / "runs"
        logs.mkdir(parents=True, exist_ok=True)
        path = logs / f"{job_id}-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.log"
        log = open(path, "ab")
        try:
            p = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, cwd=rj.ROOT,
                                 start_new_session=True)
        finally:
            log.close()
        self.ended.pop(job_id, None)
        self.runs[job_id] = {"popen": p, "message": message, "log": path, "action": action, "text": text}


def last_line(path):
    """The last `refused: ...` line of a run's output, else its last line, without the prefix (at most 300 chars)."""
    try:
        lines = [ln.strip() for ln in Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
                 if ln.strip()]
    except OSError:
        return ""
    refused = [ln for ln in lines if ln.startswith("refused: ")]
    line = (refused or lines or [""])[-1]
    return strip_refused(line)[:300]


def turn_steps(job, now=None):
    """(steps, seconds) of the turn the job is running (SPEC_ISSUE_WRITER amendment 1, A2), or None when no turn is
    open: the last STEPS_SHOWN `writer_step` events of its events.jsonl as (tool, target), read from its last
    EVENTS_TAIL bytes (a broken or cut line is skipped), and the seconds since the turn started (None when unknown).
    The targets are the model's text: the page escapes them."""
    open_turns = [st for k, st in job.data.get("stages", {}).items() if st.get("kind") == "write"
                  and st.get("status") is None]
    if not open_turns:
        return None
    st = open_turns[-1]
    steps = []
    try:
        with open(job.runs / str(st.get("run_id")) / "events.jsonl", "rb") as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - EVENTS_TAIL))
            raw = f.read()
    except OSError:
        raw = b""
    for line in raw.decode("utf-8", "replace").splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if isinstance(e, dict) and e.get("event") == "writer_step":
            steps.append((str(e.get("tool") or ""), str(e.get("target") or "")))
    seconds = None
    try:
        began = calendar.timegm(time.strptime(st.get("started_at") or "", "%Y-%m-%dT%H:%M:%SZ"))
        seconds = max(0, int((time.time() if now is None else now) - began))
    except (TypeError, ValueError):
        pass
    return steps[-STEPS_SHOWN:], seconds


def issue_cli(jobs_dir, key_file, *args):
    """The argv of an `argus issue ...` run (positionals after `--`)."""
    return [sys.executable, str(rj.ROOT / "scripts" / "argus.py"), "--jobs-dir", str(jobs_dir), "issue", *args,
            "--via", "ui", "--key-file", str(key_file), "--yes"]


class IssuePages:
    """The /issues pages; `control` is the router/control.py Control whose gates, tokens and audit they use."""

    def __init__(self, control, cfg, spawner=None, environ=os.environ):
        self.control, self.cfg, self.spawner, self.environ = control, cfg, spawner or Spawner(), environ

    # ---- reading ---------------------------------------------------------------------------------------------------

    def issue_job(self, job_id):
        job = self.control.job(job_id)
        return job if job is not None and job.data.get("kind") == "issue" else None

    def body_max(self):
        """control.message_body_max bytes (a message form), BODY_MAX when it is missing or not a whole number."""
        from router.control import BODY_MAX
        v = (self.cfg.get("control") or {}).get("message_body_max")
        return v if isinstance(v, int) and not isinstance(v, bool) and v > BODY_MAX else BODY_MAX

    def key_file(self):
        k = self.environ.get(KEY_ENV)
        return k if k else None

    def repos(self):
        return sorted((self.cfg.get("issue_writer") or {}).get("repos") or {})

    def index(self):
        rows = []
        d = self.control.jobs_dir
        for p in (sorted(d.iterdir(), reverse=True) if d.is_dir() else [])[:INDEX_MAX]:
            job = self.issue_job(p.name)
            if job is None:
                continue
            first = next((m["text"] for m in job.data.get("conversation") or [] if m["from"] == "human"), "")
            rows.append(f'<li><a href="/issues/{E(job.id)}">{E(first[:80] or job.id)}</a> '
                        f'<span class="muted">{E(str(job.data["state"]))}</span></li>')
        listing = f"<ul>{''.join(rows)}</ul>" if rows else '<p class="muted">No issue yet.</p>'
        return self._page("Issues", '<p><a href="/">Decisions</a></p><h1>Issues</h1>'
                          '<p><a class="button" href="/issues/new">New issue</a></p>'
                          f'<div class="card">{listing}</div>')

    def new_page(self, message=None, bad=False, text="", repo=""):
        if self.key_file() is None:
            return self._page("New issue", '<p><a href="/issues">Issues</a></p><h1>New issue</h1>'
                              f'<p class="bad">{E(KEY_ENV)} is not set for the service: the writer cannot run.</p>')
        token = self.control.tokens.issue("issue-new", "", "")
        options = "".join(f'<option value="{E(r)}"{" selected" if r == repo else ""}>{E(r)}</option>'
                          for r in self.repos())
        hi = int(self.cfg["issue_writer"]["message_max"])
        note = f'<p class="{"bad" if bad else "ok"}">{E(message)}</p>' if message else ""
        return self._page("New issue", f'<p><a href="/issues">Issues</a></p><h1>New issue</h1>{note}'
                          '<form class="card" method="post" action="/issues/new">'
                          f'<input type="hidden" name="token" value="{E(token)}">'
                          f'<label>Repository<select name="repo">{options}</select></label>'
                          f'<label>What do you want? (Indonesian is fine)<textarea name="message" rows="8" '
                          f'maxlength="{hi}" required>{E(text)}</textarea></label>'
                          '<button class="start" type="submit">Ask the writer</button></form>')

    def job_page(self, job, message=None, bad=False, text=""):
        """The conversation as a chat (SPEC_ISSUE_WRITER amendment 1, A3): the human's messages as bubbles, the
        writer's replies as text, the steps of a running turn, the issue in a card with Start job, the reply box."""
        d = job.data
        state = str(d["state"])
        busy = self.spawner.busy(job.id)
        sha = d.get("issue_sha256") or ""
        conv = d.get("conversation") or []
        first = next((m["text"] for m in conv if m["from"] == "human"), "")
        parts = ['<p><a href="/issues">Issues</a></p>',
                 f'<header class="chat-head"><h2 class="title">{E(first.splitlines()[0][:80] if first else job.id)}</h2>'
                 f'<p class="muted mono">{E(job.id)} · {E(d["inputs"]["repo_name"])} · {E(state)}</p></header>']
        out = self.spawner.outcome(job.id)
        if message:
            parts.append(f'<p class="{"bad" if bad else "ok"}">{E(message)}</p>')
        elif out is not None and out["code"] not in (0, 1):
            parts.append(f'<p class="bad">the last {E(out["action"])} was refused: {E(out["line"] or "no reason")}</p>')
            text = text or (out["text"] or "")
        for m in conv:
            if m["from"] == "human":
                parts.append(f'<div class="bubble"><p class="text">{E(m["text"])}</p></div>')
                continue
            extra = "".join(f'<li class="bad">clash: {E(c["file"])}:{E(str(c["line"]))} {E(c["why"])}</li>'
                            for c in m.get("clashes") or [])
            extra += "".join(f'<li>question: {E(q)}</li>' for q in m.get("questions") or [])
            parts.append(f'<div class="writer"><p class="text">{E(m["text"])}</p>'
                         f'{f"<ul>{extra}</ul>" if extra else ""}</div>')
        working = busy or state == ri.WRITING
        if working:
            run = turn_steps(job)
            steps, seconds = run if run is not None else ([], None)
            rows = "".join(f'<li><span class="dot"></span>{E(DOING.get(t, t))} <span class="mono">{E(x)}</span></li>'
                           for t, x in steps)
            took = f" ({seconds} s)" if seconds is not None else ""
            parts.append(f'<div class="steps"><ul>{rows}</ul><p class="ok">Working…{E(took)} this page reloads by '
                         'itself.</p></div>')
        text_now, _ = ri.last_issue(job)
        can_start = (not busy and state == ri.AWAITING_HUMAN and self.key_file() is not None and sha)
        if text_now:
            cap = float(self.cfg["issue_writer"].get("code_max_usd") or 0)
            start = self._form(job, "start", sha, f'<p class="muted">Starts a code job on '
                               f'{E(d["inputs"]["repo_name"])} at {E(d["inputs"]["commit"][:12])} with this issue '
                               f'({E(sha[:12])}), cap ${cap:.2f}; its draft is then yours to decide.</p>',
                               "Start job") if can_start else ""
            parts.append(f'<section class="card issue"><p class="muted">ISSUE · English · {E(sha[:12])}</p>'
                         f'<h2 class="title">{E(text_now.splitlines()[0])}</h2>'
                         f'<details><summary>The issue (English), {E(sha[:12])}</summary>'
                         f'<pre class="text">{E(text_now)}</pre></details>{start}</section>')
        if state == ri.HANDED_OFF and d.get("handoff"):
            code = d["handoff"]["job"]
            parts.append(f'<div class="card"><p>Started as job {E(code)}.</p>'
                         f'<p><a href="http://localhost:8710/jobs/{E(code)}/draft">Read its draft</a> · '
                         f'<a href="/jobs/{E(code)}">Decide</a></p></div>')
        parts.append(f'<p class="muted mono">spent ${rj.spent_nano(job) / 1e9:.4f} of '
                     f'${float(d.get("max_usd") or 0):.2f}</p>')
        if not busy:
            if self.key_file() is None and state in ri.REPLYABLE:
                parts.append(f'<p class="bad">{E(KEY_ENV)} is not set for the service: the writer cannot run.</p>')
            elif state in ri.REPLYABLE:
                hi = int(self.cfg["issue_writer"]["reply_max"])
                parts.append(self._form(job, "reply", sha, f'<label>Your reply<textarea name="message" rows="3" '
                                        f'maxlength="{hi}" required>{E(text)}</textarea></label>', "Send"))
            if d.get("handoff") and state == ri.AWAITING_HUMAN:
                parts.append('<p class="bad">A start was cut off after its code job was made: Start job again '
                             'settles it.</p>')
            elif state not in (ri.HANDED_OFF, rj.ABANDONED, ri.WRITING):
                parts.append(self._form(job, "abandon", sha, '<label>Why (optional)<input type="text" name="reason" '
                                        f'maxlength="300"></label>', "Discard"))
        return self._page(job.id, "".join(parts), refresh=REFRESH_S if working else None)

    def pending_page(self, job_id):
        """/issues/<id> before its job exists: a new run starting (reloads), one that was refused before it made the job
        (why, and the form again with the text), or None."""
        if self.spawner.busy(job_id):
            return self._page(job_id, f'<p><a href="/issues">Issues</a></p><h1>{E(job_id)}</h1>'
                              '<p class="ok">Starting the writer… this page reloads by itself.</p>', refresh=REFRESH_S)
        out = self.spawner.outcome(job_id)
        if out is None:
            return None
        return self.new_page(f"the writer could not start: {out['line'] or 'no reason'}", bad=True,
                             text=out["text"] or "")

    def _form(self, job, action, sha, inner, label):
        token = self.control.tokens.issue(f"issue-{action}", job.id, sha)
        return (f'<form class="card" method="post" action="/issues/{E(job.id)}/{action}">'
                f'<input type="hidden" name="token" value="{E(token)}">'
                f'<input type="hidden" name="sha" value="{E(sha[:12])}">{inner}'
                f'<button class="{action}" type="submit">{E(label)}</button></form>')

    def _page(self, title, body, refresh=None):
        from router.control import page
        out = page(title, body)
        if refresh:
            out = out.replace(b"<head>", f'<head><meta http-equiv="refresh" content="{int(refresh)}">'.encode(), 1)
        return out

    # ---- acting ----------------------------------------------------------------------------------------------------

    def act(self, job_id, action, headers, body):
        """Host was checked by the handler; the rest of F3 here, in order. Returns (status, page)."""
        c = self.control
        rec = {"path": (f"/issues/{job_id}/{action}" if job_id else "/issues/new")[:200]}

        def refuse(status, gate, why, job=None, text="", repo=""):
            c.audit(**rec, refused=gate, why=why)
            if job is not None:
                return status, self.job_page(job, f"refused: {why}", bad=True, text=text)
            if action == "new" and gate not in ("origin", "path"):
                return status, self.new_page(f"refused: {why}", bad=True, text=text, repo=repo)
            return status, self._page("refused", f'<p class="bad">refused: {E(why)}</p><p><a href="/issues">Issues</a></p>')

        why = c.origin_problem(headers)
        if why:
            rec["origin"] = (headers.get("Origin") or "")[:100] if headers.get("Origin") is not None else None
            return refuse(403, "origin", why)
        job = None
        if action != "new":
            job = self.issue_job(job_id)
            if job is None or action not in ISSUE_ACTIONS:
                return refuse(404, "path", "no such issue job or action")
            rec["job"] = job.id
        if body is None:
            return refuse(413, "form", "the form is too large", job)
        try:
            form = parse_qs(body.decode("utf-8", "replace"), keep_blank_values=True, max_num_fields=8)
        except ValueError:
            return refuse(400, "form", "too many fields", job)
        values = {}
        for k in FIELDS[action]:
            v = form.get(k) or [""]
            if len(v) != 1:
                return refuse(400, "form", "a field was sent twice", job)
            values[k] = v[0]
        text = normalize(values.get("message", ""))
        repo = values.get("repo", "")
        # the form before the token: what was typed comes back with the refusal and the page's token is kept
        why = None
        if action in ("new", "reply"):
            why = ri.message_problem(self.cfg, text, first=action == "new")
        if action == "new" and repo not in self.repos():
            why = f"repository {repo!r} is not one the writer reads"
        if action == "abandon":
            from router.control import reason_problem
            values["reason"] = values["reason"].strip(" ")
            why = reason_problem(values["reason"], required=False)
        if action != "new" and values["sha"] and not re.fullmatch(r"[0-9a-f]{12}", values["sha"]):
            why = "the issue sha is not 12 hex characters"
        if why:
            return refuse(400, "form", why, job, text, repo)
        sha_now = (job.data.get("issue_sha256") or "") if job is not None else ""
        if job is not None and values["sha"] != sha_now[:12]:          # before the token, so the reason is this one
            return refuse(409, "issue", "the issue changed since the page was opened: read it again", job, text)
        why = c.tokens.spend(values["token"], f"issue-{action}", job.id if job else "", sha_now)
        if why:
            return refuse(403, "token", why, job, text, repo)
        if action == "abandon":
            c.audit(**rec, attempt=action)
            code, line = c.run("abandon", job.id, values["reason"] or "discarded from the phone", "", c.jobs_dir)
            c.audit(**rec, action=action, exit=code, line=line)
            fresh = self.issue_job(job.id) or job
            return (200, self.job_page(fresh, "discarded")) if code == 0 else \
                (409, self.job_page(fresh, f"refused: {strip_refused(line) or 'the command failed'}", bad=True))
        key = self.key_file()
        if key is None:
            return refuse(409, "key", f"{KEY_ENV} is not set for the service", job, text, repo)
        new_id = rj.new_job_id() if action == "new" else job.id
        if self.spawner.busy(new_id):
            return refuse(409, "busy", "the writer is still working on this job", job, text)
        message = self.spawner.message_file(text) if action in ("new", "reply") else None
        if action == "new":
            argv = issue_cli(c.jobs_dir, key, "new", "--repo", repo, "--job-id", new_id, "--message-file", str(message))
        elif action == "reply":
            argv = issue_cli(c.jobs_dir, key, "reply", "--message-file", str(message)) + ["--", job.id]
        else:
            argv = issue_cli(c.jobs_dir, key, "start", "--sha", values["sha"]) + ["--", job.id]
        rec["job"] = new_id
        c.audit(**rec, attempt=action, sha=values.get("sha") or None)
        self.spawner.spawn(new_id, argv, message, action=action, text=text if action in ("new", "reply") else None)
        c.audit(**rec, action=action, started=True)
        body = (f'<p class="ok">{"Asked the writer" if action != "start" else "Started"}: job {E(new_id)}.</p>'
                f'<p><a href="/issues/{E(new_id)}">Open it</a></p>')
        out = self._page("started", body).replace(
            b"<head>", f'<head><meta http-equiv="refresh" content="2;url=/issues/{E(new_id)}">'.encode(), 1)
        return 200, out
