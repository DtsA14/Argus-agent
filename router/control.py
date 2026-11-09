"""The control service of the phone (docs/reviews/SPEC_CONTROL_UI.md section 4a, phase 2): reject and abandon a job.

  argus control serve      forever, on 127.0.0.1:8711 only (systemd --user argus-control)

It is harness code and the only way an action reaches a job from the phone; the viewer's proxy on 8710 stays GET-only
and never forwards anything here. Every action is the same CLI a human types (F3.5: `scripts/argus.py reject|abandon
... --sha ... --via ui`), so the job's lock, its state gate and the check of the draft sha stay in router/job.py. Before
that, every POST passes the gates of F3 in order: Host, Origin (and Sec-Fetch-Site), a one-time token of this page, the
form. Every POST is one line of audit (F5). The service holds no key and runs no model.
"""
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import subprocess
import sys
import time
import unicodedata
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from router import job as rj

BIND, PORT = "127.0.0.1", 8711                    # F1: fixed, never 0.0.0.0 or "localhost", never 8000 or 8710
HOSTS = ("127.0.0.1:8711", "localhost:8711")
ORIGINS = ("http://127.0.0.1:8711", "http://localhost:8711")
UI_ID = re.compile(r"j[0-9]{8}_[0-9]{6}_[0-9a-f]{4}")    # fullmatch      # F2: stricter than rj.JOB_ID, the shape `argus code` makes
TOKEN_TTL = 30 * 60                                # F3.3: seconds a page's token is good for
BODY_MAX = 4096                                    # F2: bytes of a POST body
REASON_MAX = 300                                   # F2: characters of a reason
ABANDON_DEFAULT = "abandoned from the phone"
CLI_TIMEOUT = 120
ARGUS = rj.ROOT / "scripts" / "argus.py"
AUDIT = Path.home() / ".local" / "state" / "argus-control" / "audit.jsonl"
# The states a job is listed in (F2), and the actions each state allows: the CLI's own gates, shown, not enforced here.
REJECTABLE = (rj.AWAITING_APPROVAL, rj.DRAFT_FAILED, rj.REVIEW_READY, rj.REVIEW_INVALID, rj.AWAITING_RESEARCH_REVIEW)
NOT_ABANDONABLE = (rj.REVIEW_READY, rj.REVIEW_INVALID, rj.REJECTED, rj.ABANDONED, rj.APPLIED)
ACTIONS = ("reject", "abandon")
HEADERS = {
    "Content-Security-Policy": "default-src 'none'; style-src 'self'; form-action 'self'; frame-ancestors 'none'; "
                               "base-uri 'none'",
    "X-Frame-Options": "DENY",
    # Not no-referrer: with it a browser sends `Origin: null` on a POST, even from the same page (Fetch, "append a
    # request Origin header"), and F3.2 refuses every form (control p1, Atha's first reject from Safari, 2026-11-09).
    # same-origin still sends no referrer to another site.
    "Referrer-Policy": "same-origin",
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
}
STYLE = (b"body{margin:0;padding:16px;background:#0a0e13;color:#e8eef4;font:16px system-ui,sans-serif}"
         b"a{color:#7db4ff}.card{background:#11171f;border:1px solid #232d39;border-radius:1.25rem;padding:1rem;"
         b"margin:0 0 .75rem}.muted{color:#93a1b0;font-size:.85rem}.sha{font-family:monospace;color:#f5c46b}"
         b"input[type=text]{width:100%;box-sizing:border-box;min-height:2.75rem;padding:.5rem;margin:.5rem 0;"
         b"color:inherit;background:#18202a;border:1px solid #232d39;border-radius:.75rem;font:inherit}"
         b"button{min-height:2.75rem;padding:0 1rem;border:0;border-radius:.75rem;font:inherit;font-weight:600}"
         b".reject{background:#f26d6d;color:#0a0e13}.abandon{background:#232d39;color:#e8eef4}"
         b".bad{color:#f26d6d}.ok{color:#6ee7b7}ul{padding:0;list-style:none}li{margin:.5rem 0}"
         b"h1{font-size:1.15rem;font-family:monospace;overflow-wrap:anywhere}"
         b"textarea,select{width:100%;box-sizing:border-box;padding:.5rem;margin:.5rem 0;color:inherit;"
         b"background:#18202a;border:1px solid #232d39;border-radius:.75rem;font:inherit}select{min-height:2.75rem}"
         b".text{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit;margin:0}"
         b".start,.reply{background:#7db4ff;color:#0a0e13}.button{display:inline-block;padding:.6rem 1rem;"
         b"background:#7db4ff;color:#0a0e13;border-radius:.75rem;font-weight:600;text-decoration:none}"
         b".human{border-left:3px solid #7db4ff}summary{cursor:pointer;min-height:2.75rem}")


class Tokens:
    """F3.3: HMAC-SHA256 of `action|job|sha|issued` under a secret made at start and kept in memory only, good for
    TOKEN_TTL seconds and once. A restart forgets the secret, so every page open before it is refused."""

    def __init__(self, clock=time.time):
        self.secret = secrets.token_bytes(32)
        self.clock = clock
        self.used = {}                             # mac of a spent token -> when it expires, pruned as they expire

    def _mac(self, action, job, sha, issued):
        return hmac.new(self.secret, f"{action}|{job}|{sha}|{issued}".encode(), hashlib.sha256).hexdigest()

    def issue(self, action, job, sha):
        issued = int(self.clock())
        return f"{issued}.{self._mac(action, job, sha, issued)}"

    def spend(self, token, action, job, sha):
        """None when the token is good (and it is spent now), else why not."""
        now = self.clock()
        self.used = {t: until for t, until in self.used.items() if until > now}
        issued, _, mac = (token or "").partition(".")
        # One spelling per token (security review: `0<issued>` would be a fresh string for a spent token).
        if not re.fullmatch(r"[1-9][0-9]{0,11}", issued) or not re.fullmatch(r"[0-9a-f]{64}", mac):
            return "no token of this page"
        if not hmac.compare_digest(mac, self._mac(action, job, sha, int(issued))):
            return "the token is not this page's (or the service restarted): open the page again"
        if not 0 <= now - int(issued) <= TOKEN_TTL:
            return "the page is too old: open it again"
        if mac in self.used:
            return "this page was already sent once: open it again"
        self.used[mac] = int(issued) + TOKEN_TTL + 1
        return None


def reason_problem(reason, required):
    if not reason:
        return "a reason is required" if required else None
    if len(reason) > REASON_MAX:
        return f"the reason has {len(reason)} characters, more than {REASON_MAX}"
    # Control, format (bidi), private and unassigned characters and the line/paragraph separators (code review)
    if any(unicodedata.category(c)[0] == "C" or unicodedata.category(c) in ("Zl", "Zp") for c in reason):
        return "the reason must be one line without control characters"
    return None


class Unreadable(Exception):
    pass


def draft_sha12(job):
    """The sha12 of the job's last draft, None when it has none; Unreadable when it has one that cannot be read (never
    taken for "no draft", which would act without the sha check)."""
    try:
        _, path = rj._last_draft(job)
    except rj.Refused:
        return None
    try:
        return rj.draft_sha(path)[:12]
    except (OSError, ValueError) as e:
        raise Unreadable(f"the draft cannot be read: {type(e).__name__}") from None


def allowed(state):
    return [a for a in ACTIONS if (state in REJECTABLE if a == "reject" else state not in NOT_ABANDONABLE)]


def cli(action, job_id, reason, sha, jobs_dir):
    """F3.5: the CLI a human types, as a child process (argv, never a shell); `--` before the positionals so a reason
    that starts with '-' stays a reason."""
    argv = [sys.executable, str(ARGUS), "--jobs-dir", str(jobs_dir), action, "--via", "ui",
            *(["--sha", sha] if sha else []), "--", job_id, reason]
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=CLI_TIMEOUT, cwd=rj.ROOT)
    except subprocess.TimeoutExpired:
        return None, "the command did not finish in time"
    out = (r.stdout if r.returncode == 0 else r.stderr or r.stdout) or ""
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    line = (lines[0] if r.returncode == 0 else lines[-1]) if lines else ""
    return r.returncode, line[:300]


def strip_refused(line):
    """A CLI line without its own `refused: ` (the page adds one)."""
    return line[len("refused: "):] if line.startswith("refused: ") else line


def page(title, body):
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" '
            f'content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title>'
            f'<link rel="stylesheet" href="/style.css"></head><body>{body}</body></html>').encode()


class Control:
    """The service's state: where the jobs are, its tokens and its audit file."""

    def __init__(self, jobs_dir, audit=AUDIT, clock=time.time, run=cli):
        self.jobs_dir, self.audit_path, self.tokens, self.run = Path(jobs_dir), Path(audit), Tokens(clock), run
        self.clock = clock
        self.issues = None                         # router/control_issues.IssuePages, when the config has a writer

    def origin_problem(self, headers):
        """F3.2: why a POST did not come from this service's own page, or None."""
        if headers.get("Origin") not in ORIGINS:
            return "this page did not come from the control service"
        if headers.get("Sec-Fetch-Site") not in (None, "same-origin"):
            return "a cross-site request"
        return None

    def audit(self, **rec):
        """F5: one JSON line per POST, never the token."""
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.clock())), **rec}
        with open(self.audit_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, sort_keys=True) + "\n")

    def job(self, job_id):
        """The job of a path segment, or None: the UI shape first, so nothing else reaches the disk."""
        if not UI_ID.fullmatch(job_id or ""):
            return None
        try:
            return rj.open_job(job_id, self.jobs_dir)
        except (rj.Refused, OSError, ValueError):
            return None

    def index(self):
        rows = []
        for d in sorted(self.jobs_dir.iterdir(), reverse=True) if self.jobs_dir.is_dir() else []:
            job = self.job(d.name)
            if job is not None and job.data.get("state") in REJECTABLE:
                rows.append(f'<li><a href="/jobs/{html.escape(job.id)}">{html.escape(job.id)}</a> '
                            f'<span class="muted">{html.escape(str(job.data["state"]))}</span></li>')
        listing = f"<ul>{''.join(rows)}</ul>" if rows else '<p class="muted">Nothing waits for a decision.</p>'
        issues = '<p><a class="button" href="/issues">Issues</a></p>' if self.issues is not None else ""
        return page("Argus control", f'<h1>Argus control</h1>{issues}<div class="card">{listing}</div>')

    def job_page(self, job, message=None, bad=False, reason=""):
        e = html.escape
        state = str(job.data.get("state"))
        try:
            sha = draft_sha12(job)
        except Unreadable as why:
            return page(job.id, f'<p><a href="/">All</a></p><h1>{e(job.id)}</h1><p class="bad">{e(str(why))}</p>')
        parts = [f'<p><a href="/">All</a></p><h1>{e(job.id)}</h1><div class="card"><p>{e(state)}</p>',
                 f'<p>draft <span class="sha">{e(sha)}</span></p>' if sha else "",
                 f'<p class="muted">job spent ${rj.spent_nano(job) / 1e9:.4f} of its cap ${float(job.data.get("max_usd") or 0):.2f}'
                 f'</p><p><a href="http://localhost:8710/jobs/{e(job.id)}/draft">Read the draft</a></p></div>']
        if message:
            parts.insert(0, f'<p class="{"bad" if bad else "ok"}">{e(message)}</p>')
        for action in allowed(state):
            token = self.tokens.issue(action, job.id, sha or "")
            need = action == "reject"
            parts.append(
                f'<form class="card" method="post" action="/jobs/{e(job.id)}/{action}">'
                f'<input type="hidden" name="token" value="{e(token)}"><input type="hidden" name="sha" value="{e(sha or "")}">'
                f'<label>{"Why (required)" if need else "Why (optional)"}<input type="text" name="reason" '
                f'value="{e(reason)}" maxlength="{REASON_MAX}"{" required" if need else ""}></label>'
                f'<button class="{action}" type="submit">{action.capitalize()}</button></form>')
        if not allowed(state):
            parts.append('<p class="muted">No action for this state.</p>')
        return page(job.id, "".join(parts))

    def act(self, job_id, action, headers, body):
        """F3, in order; returns (status, page). Nothing reaches the CLI before every gate passed."""
        rec = {"path": f"/jobs/{job_id}/{action}"[:200]}

        def refuse(status, gate, why, job=None, reason=""):
            self.audit(**rec, refused=gate, why=why)
            if job is not None:
                return status, self.job_page(job, f"refused: {why}", bad=True, reason=reason)
            return status, page("refused", f'<p class="bad">refused: {html.escape(why)}</p><p><a href="/">All</a></p>')

        why = self.origin_problem(headers)
        if why:
            origin = headers.get("Origin")
            rec["origin"] = (origin or "")[:100] if origin is not None else None
            return refuse(403, "origin", why)
        job = self.job(job_id)
        if job is None or action not in ACTIONS:
            return refuse(404, "path", "no such job or action")
        rec["job"] = job.id
        if body is None:
            return refuse(413, "form", "the form is too large", job)
        try:
            form = parse_qs(body.decode("utf-8", "replace"), keep_blank_values=True, max_num_fields=8)
        except ValueError:
            return refuse(400, "form", "too many fields", job)
        one = lambda k: (form.get(k) or [""])[0] if len(form.get(k) or [""]) == 1 else None
        token, sha, reason = one("token"), one("sha"), one("reason")
        if token is None or sha is None or reason is None:
            return refuse(400, "form", "a field was sent twice", job)
        # The form before the token (code review): a reason refused for its shape keeps the page's token and is
        # written back into the form, so nothing typed is lost.
        reason = reason.strip(" ")                 # only spaces: a control character at an end is refused, not cut
        why = reason_problem(reason, required=action == "reject")
        if sha and not re.fullmatch(r"[0-9a-f]{12}", sha):
            why = "the draft sha is not 12 hex characters"
        if why:
            return refuse(400, "form", why, job, reason)
        why = self.tokens.spend(token, action, job.id, sha)
        if why:
            return refuse(403, "token", why, job, reason)
        # F2/F4: a job with a draft is acted on only with the sha of the draft it has now, also when the page was
        # opened before the draft existed (code review: the CLI skips its check without --sha).
        try:
            current = draft_sha12(job) or ""
        except Unreadable as e:
            return refuse(409, "draft", str(e), job, reason)
        if sha != current:
            return refuse(409, "draft", "the draft changed since the page was opened: read it again", job, reason)
        self.audit(**rec, attempt=action, sha=sha or None)          # before the job changes (F5)
        code, line = self.run(action, job.id, reason or ABANDON_DEFAULT, sha, self.jobs_dir)
        self.audit(**rec, action=action, sha=sha or None, exit=code, line=line)
        fresh = self.job(job.id) or job
        if code == 0:
            return 200, self.job_page(fresh, {"reject": "rejected", "abandon": "abandoned"}[action])
        return 409, self.job_page(fresh, f"refused: {strip_refused(line) or 'the command failed'}", bad=True)


class Handler(BaseHTTPRequestHandler):
    control = None                                 # set by serve()
    server_version = "argus-control"
    timeout = 10                                   # a stalled client never holds the one-request server (code review)
    sys_version = ""

    def end_headers(self):                         # every answer, errors of the base class included
        for k, v in HEADERS.items():
            self.send_header(k, v)
        super().end_headers()

    def log_message(self, *a):                     # the audit is the record; no request log on stderr
        pass

    def _send(self, status, body, ctype="text/html; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _host_ok(self, audit=False):
        if self.headers.get("Host") in HOSTS:
            return True
        if audit:
            self.control.audit(path=self.path[:200], refused="host", why="wrong host")
        self._send(421, page("refused", '<p class="bad">refused: wrong host</p>'))
        return False

    def do_GET(self):
        if not self._host_ok():
            return
        path = self.path.split("?", 1)[0]
        if path == "/":
            return self._send(200, self.control.index())
        if path == "/style.css":
            return self._send(200, STYLE, "text/css; charset=utf-8")
        issues = self.control.issues
        if issues is not None and path == "/issues":
            return self._send(200, issues.index())
        if issues is not None and path == "/issues/new":
            return self._send(200, issues.new_page())
        m = re.fullmatch(r"/issues/([^/]+)", path)
        if issues is not None and m:
            job = issues.issue_job(m.group(1))
            if job is not None:
                return self._send(200, issues.job_page(job))
            pending = issues.pending_page(m.group(1)) if UI_ID.fullmatch(m.group(1)) else None
            if pending is not None:                # a new job the background run has not made (yet, or ever)
                return self._send(200, pending)
            return self._send(404, page("not found", '<p>not found</p><p><a href="/issues">Issues</a></p>'))
        m = re.fullmatch(r"/jobs/([^/]+)", path)
        job = self.control.job(m.group(1)) if m else None
        if job is None:
            return self._send(404, page("not found", '<p>not found</p><p><a href="/">All</a></p>'))
        return self._send(200, self.control.job_page(job))

    def do_POST(self):
        if not self._host_ok(audit=True):
            return
        m = re.fullmatch(r"/jobs/([^/]+)/([a-z]+)", self.path)
        issue = re.fullmatch(r"/issues/new|/issues/([^/]+)/([a-z]+)", self.path)
        issues = self.control.issues
        limit = issues.body_max() if issue and issues else BODY_MAX
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        body = self.rfile.read(length) if 0 <= length <= limit else None
        if body is None:
            self.close_connection = True
        if issue and issues is not None:
            action = "new" if self.path == "/issues/new" else issue.group(2)
            status, out = issues.act(None if action == "new" else issue.group(1), action, self.headers, body)
            return self._send(status, out)
        if not m:
            self.control.audit(path=self.path[:200], refused="path", why="no such action")
            return self._send(404, page("not found", "<p>not found</p>"))
        status, out = self.control.act(m.group(1), m.group(2), self.headers, body)
        self._send(status, out)

    def _not_allowed(self):
        self.send_response(405)
        self.send_header("Allow", "GET, POST")
        self.send_header("Content-Length", "0")
        self.end_headers()

    do_PUT = do_DELETE = do_PATCH = do_OPTIONS = do_HEAD = _not_allowed


def server(control, port=PORT):
    handler = type("Bound", (Handler,), {"control": control})
    return HTTPServer((BIND, port), handler)


def serve(jobs_dir, cfg=None):
    """`argus control serve`: forever, one request at a time. cfg: the config, for the issue writer's pages."""
    control = Control(jobs_dir)
    if cfg is not None and cfg.get("issue_writer"):
        from router.control_issues import IssuePages
        control.issues = IssuePages(control, cfg)
    srv = server(control)
    print(f"argus control on http://{BIND}:{PORT} (jobs {jobs_dir})", flush=True)
    srv.serve_forever()
