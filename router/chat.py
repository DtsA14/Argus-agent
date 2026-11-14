"""The chat app of the phone, C1 (docs/reviews/SPEC_CHAT_APP.md, sections 3 and 11): read only, no POST, no model.

  argus chat serve         forever, on 127.0.0.1:8712 only (systemd --user argus-chat)

Trusted code (written in the strict lane, never by an Argus agent). It shows the jobs' state, cost and stages from the same
allowlisted projection the staging snapshot uses (router/stage_data.py `_one`: read through directory fds, never through
a symlink, every value checked, no key pattern), and serves a page that renders them as text. It has no route that changes
anything: every method but GET is refused, and it holds no key and runs no model.

Checks on every request, GET included (11.1, 11.2): the Host is exactly 127.0.0.1:PORT; on /api/* Sec-Fetch-Site is absent,
same-origin or none (same-site is the viewer on localhost:8710 and is refused); no cookie is ever set or read.
"""
import hashlib
import io
import json
import os
import re
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from router import job as rj
from router import stage_data as sd

BIND, PORT = "127.0.0.1", 8712                    # SPEC_CHAT_APP 2: 8712 while the chat is built, 8711 at C4 (one value)
HOSTS = (f"{BIND}:{PORT}",)                        # never "localhost": the viewer is localhost:8710 and shares its cookie jar
UI_ID = re.compile(r"j[0-9]{8}_[0-9]{6}_[0-9a-f]{4}")
TOTAL_S = 10                                       # a whole request, not one read: a client dripping a byte per 8 s is cut at this
LIST_MAX = 100                                     # the single-threaded server reads at most this many job.json per request
STATIC_DIR = Path(__file__).resolve().parent / "chat_static"
STATIC_TYPES = {"index.html": "text/html; charset=utf-8", "app.js": "text/javascript; charset=utf-8",
                "app.css": "text/css; charset=utf-8"}
# The shipped files are pinned (like the viewer's sw.js): changing one means changing this line in the same change.
STATIC_SHA256 = {
    "index.html": "20b7ff061209d34c8a391b19b8b5d39f32a8565733cb6138ca3f0e057551f90d",
    "app.js": "e5388ebfeac272d3414b081c8f6aee8dbc74d17fa048d95a02dcad9aaa8ff24b",
    "app.css": "4c27275837abc6c2277a5b570e5b1c9e65e9ea5fa629f06983828451b2a0cfc5",
}


def csp(port=PORT):
    return ("default-src 'none'; script-src http://127.0.0.1:%d/static/app.js; style-src 'self'; connect-src 'self'; "
            "img-src 'self'; form-action 'none'; frame-ancestors 'none'; base-uri 'none'; worker-src 'none'; "
            "require-trusted-types-for 'script'; trusted-types 'none'" % port)


HEADERS = {
    "Content-Security-Policy": csp(),
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Cross-Origin-Opener-Policy": "same-origin",
}


def load_static():
    """{name: bytes} of the shipped files; refuses to start when one is not the pinned one."""
    out = {}
    for name in STATIC_TYPES:
        data = (STATIC_DIR / name).read_bytes()
        if STATIC_SHA256 and hashlib.sha256(data).hexdigest() != STATIC_SHA256.get(name):
            raise RuntimeError(f"chat_static/{name} is not the pinned file")
        out[name] = data
    return out


def card(raw):
    """One job of the list: the projected job's few fields (the projection already checked every value and the title)."""
    stages = raw.get("stages") or {}
    done_usd = sum(s["usd"] for s in stages.values() if isinstance(s.get("usd"), (int, float)))
    return {"id": raw.get("job"), "kind": raw.get("kind"), "state": raw.get("state"), "created_at": raw.get("created_at"),
            "title": raw.get("title"), "max_usd": raw.get("max_usd"), "stages_usd": round(done_usd, 6),
            "stages": len(stages)}


class Chat:
    def __init__(self, jobs_dir, clock=time.time):
        self.jobs_dir, self.clock = Path(jobs_dir), clock
        self.static = load_static()

    def _source(self):
        return os.open(self.jobs_dir, os.O_RDONLY | os.O_DIRECTORY)

    def names(self):
        """Every directory name that has the UI job shape, newest first (nothing else reaches the disk)."""
        try:
            return sorted((n for n in os.listdir(self.jobs_dir) if UI_ID.fullmatch(n)), reverse=True)
        except OSError:
            return []

    def threads(self):
        out, skipped = [], 0
        try:
            sfd = self._source()
        except OSError:
            return {"threads": [], "skipped": 0}
        try:
            for name in self.names()[:LIST_MAX]:
                try:
                    jfd = sd._open_dir(name, sfd)
                    try:
                        raw = json.loads(sd._read_at(jfd, "job.json", limit=sd.READ_MAX))
                    finally:
                        os.close(jfd)
                    out.append(card(sd.project_job(raw, name)))
                except (OSError, ValueError, sd.Excluded):
                    skipped += 1                   # never with a value: a job that cannot be shown is counted
        finally:
            os.close(sfd)
        return {"threads": out, "skipped": skipped}

    def thread(self, job_id):
        """The detail of one job (projected job, its cost from its ledgers), or None. Known limit (Opus review 2026-11-14): `_one`
        reads more than is shown (every ledger, and the draft files it then drops), unbounded per file up to READ_MAX; nothing of it
        is exposed. 11.13 asks for a fixed file list and about 256 KB per text: do that before C3 (research reports)."""
        if not UI_ID.fullmatch(job_id or ""):
            return None
        try:
            sfd = self._source()
        except OSError:
            return None
        try:
            got = sd._one(sfd, job_id, [], [])
        finally:
            os.close(sfd)
        if got is None:
            return None
        job, _runs, nano, _files = got
        return {"job": {**card(job), "stages": job.get("stages", {}), "log": job.get("log", [])},
                "spent_usd": nano / 1e9}

    def status(self):
        t = self.threads()["threads"]
        by = {}
        for c in t:
            by[c["state"]] = by.get(c["state"], 0) + 1
        total = len(self.names())
        return {"jobs": total, "shown": len(t), "capped": total > LIST_MAX, "by_state": by, "now": int(self.clock())}


class _DeadlineRaw(io.RawIOBase):
    """The socket as a raw file whose every recv waits only for what is left of TOTAL_S: a client that drips a byte per
    8 s inside one line is cut when the whole request has taken too long (the socket timeout alone is per recv)."""

    def __init__(self, sock, deadline):
        self.sock, self.deadline = sock, deadline

    def readable(self):
        return True

    def readinto(self, b):
        left = self.deadline - time.monotonic()
        if left <= 0:
            raise TimeoutError("the request took too long")
        self.sock.settimeout(left)
        return self.sock.recv_into(b)


class Handler(BaseHTTPRequestHandler):
    server_version = "argus-chat"
    timeout = 10
    sys_version = ""
    chat = None

    def setup(self):
        super().setup()
        self.deadline = time.monotonic() + TOTAL_S
        self.rfile = io.BufferedReader(_DeadlineRaw(self.connection, self.deadline), 65536)

    def parse_request(self):
        if not super().parse_request():
            return False
        if self.request_version == "HTTP/0.9":              # an HTTP/0.9 answer has no headers at all: none is given
            self.close_connection = True
            return False
        return True

    def __getattr__(self, name):                             # every method but GET, TRACE and CONNECT included (11.1)
        if name.startswith("do_"):
            return self._not_allowed
        raise AttributeError(name)

    def end_headers(self):
        for k, v in HEADERS.items():
            self.send_header(k, v)
        super().end_headers()

    def log_message(self, *a):
        pass

    def _send(self, status, body, ctype="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status, obj):
        self._send(status, json.dumps(obj, sort_keys=True).encode(), "application/json")

    def _refuse(self, status, why):
        self._json(status, {"refused": why})

    def _host_ok(self):
        """Exactly one Host header, and it is ours (SPEC_PWA_VIEWER A: two Host headers are a 421): the first of two must
        not stand in for the second, which a proxy or a rebinding page may have chosen."""
        hosts = self.headers.get_all("Host") or []
        return len(hosts) == 1 and hosts[0] in HOSTS

    def do_GET(self):
        if not self._host_ok():                              # every method, every route (11.1): reads are private too
            return self._refuse(421, "wrong host")
        path = self.path
        if path.startswith("/api/"):
            sites = self.headers.get_all("Sec-Fetch-Site") or []
            if len(sites) > 1 or (sites and sites[0] not in ("same-origin", "none")):
                return self._refuse(403, "not a request of the chat's own page")
            return self._api(path)
        names = {"/": "index.html", "/static/app.js": "app.js", "/static/app.css": "app.css"}
        if path in names:
            return self._send(200, self.chat.static[names[path]], STATIC_TYPES[names[path]])
        return self._refuse(404, "not found")

    def _api(self, path):
        if path == "/api/status":
            return self._json(200, self.chat.status())
        if path == "/api/threads":
            return self._json(200, self.chat.threads())
        m = re.fullmatch(r"/api/threads/([^/?#%]+)", path)
        if m:
            got = self.chat.thread(m.group(1))
            return self._json(200, got) if got is not None else self._refuse(404, "not found")
        return self._refuse(404, "not found")

    def _not_allowed(self):
        if not self._host_ok():
            return self._refuse(421, "wrong host")
        self.close_connection = True                         # a body we never read must not be taken for the next request
        self.send_response(405)
        self.send_header("Allow", "GET")
        self.send_header("Content-Length", "0")
        self.end_headers()



def server(chat, port=PORT):
    handler = type("Bound", (Handler,), {"chat": chat})
    return HTTPServer((BIND, port), handler)


def serve(jobs_dir):
    chat = Chat(jobs_dir)
    srv = server(chat)
    print(f"argus chat on http://{BIND}:{PORT} (jobs {jobs_dir})", flush=True)
    srv.serve_forever()
