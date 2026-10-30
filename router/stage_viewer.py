"""The viewer on staging (docs/reviews/SPEC_PWA_VIEWER.md §4 S and §8 A1-A5, Atha 2026-10-30): argus-viewer, a static
React PWA, as the second staging app next to argus-ledger. No model is called here, and no agent has a tool for it.

  argus stage viewer-deploy <job>   the job's applied commit (as reviewed), built by `vite build` in pwa_node22 with no
                                    network on a read-only archive; the dist is checked (A4, A3, E1) and smoke-tested
                                    through a proxy of its own before `current` is swapped to it
  argus stage viewer-rollback       `current` swapped back to the release that was live before, checked the same way
  argus stage viewer-status         what is live and what a rollback would publish
  argus stage viewer-smoke          S3 against the always-on proxy, including that 127.0.0.1:8710 is its only listener
  argus stage proxy                 the proxy (systemd --user, deploy/systemd/argus-stage-proxy.service)

Layout under ~/argus-staging/apps/viewer (its own state; argus-ledger's state.json and releases are never touched, and
a viewer command never starts or stops a container):
  releases/<job>-<commit12>/   the dist, read-only; recorded in releases.jsonl with its image and the sha of each file
  current -> releases/<...>    relative symlink, replaced with rename(): the proxy serves the old or the new release
  state.json                   {"live", "history"}, as argus-ledger's
  .build-*                     a build in progress (the archive and /out); removed whatever happens

The proxy (S2) listens on 127.0.0.1:8710 only and answers GET/HEAD for Host localhost:8710 or 127.0.0.1:8710. Three API
paths go to the live argus-ledger release's socket (its container's pid, SO_PEERCRED) in a request of its own (A1, A2);
any other path is a file of the published release, opened without following links. It writes nothing.
"""
import fcntl
import hashlib
import http.client
import http.server
import json
import os
import posixpath
import re
import secrets
import shutil
import stat
import subprocess
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import unquote

from acceptance import validation as va
from acceptance.workspace import digest, snapshot

from . import job as rj
from . import stage as sg
from . import stage_data as sd

ENVIRONMENT = "pwa_node22"
LOCK_FILE = sg.ROOT / "environments" / ENVIRONMENT / "package-lock.json"
BIND, PORT = "127.0.0.1", 8710                     # Atha 2026-10-30: explicit, never 0.0.0.0 or "localhost"; never 8000
# The service worker as reviewed (A3): the sha256 of public/sw.js of the argus-viewer skeleton (commit 505e23b, network
# first app shell, never /api/), a copy of which is fixtures/repos/viewer_demo/public/sw.js. A release whose sw.js
# differs is never published. Changing it is a strict-lane change of this file.
SW_SHA256 = "db58777a410480de1dac10c17f730396dcaee0031ea693dbd03e2db418c7e0cf"
BUILD_TIMEOUT_S = 300
BUILD_ARGV = ["node", "/node_modules/vite/bin/vite.js", "build", "--configLoader", "runner", "--outDir", "/out",
              "--emptyOutDir", "--logLevel", "warn"]
BUILD_LIMITS = ["--memory", "512m", "--memory-swap", "512m", "--pids-limit", "128", "--cpus", "1"]
BUILD_PREFIX = "argus-staging-viewer-build-"

# A4: what a dist may hold.
TEXT = {".html", ".js", ".css", ".webmanifest", ".json", ".svg", ".txt"}
MAGIC = {".png": b"\x89PNG\r\n\x1a\n", ".ico": b"\x00\x00\x01\x00"}
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".webmanifest": "application/manifest+json", ".json": "application/json", ".svg": "image/svg+xml",
         ".txt": "text/plain; charset=utf-8", ".png": "image/png", ".ico": "image/x-icon"}
SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")
MAX_DEPTH, MAX_FILE, MAX_TOTAL, MAX_FILES = 4, 2 * 1024 * 1024, 5 * 1024 * 1024, 200
# A3: browser storage outside the service worker. A text scan: it finds ordinary use, not a disguised one
# (window["local" + "Storage"]); the app's code is reviewed in the fast lane all the same.
STORAGE = re.compile(rb"localStorage|sessionStorage|indexedDB|caches\.|CacheStorage")
DEP_KINDS = ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies")

# S2, A1: the proxy.
API = re.compile(r"^/api/(summary|jobs|jobs/(" + sd.JOB_ID.pattern.strip("^$") + r"))$")
SECURITY = {"Content-Security-Policy": "default-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; "
                                       "base-uri 'none'; frame-ancestors 'none'",
            "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"}
MAX_ANSWER = 1_000_000
STATE_PROBLEM = "viewer state: "                            # how status() starts when state.json cannot be used
CURRENT = re.compile(r"^releases/(" + sg.RELEASE.pattern.strip("^$") + r")$")
REFS = re.compile(rb"""(?:src|href)\s*=\s*["']([^"'?#]*)""")


class Refused(rj.Refused):
    pass


# ---- E1, A4, A3: checks ----------------------------------------------------------------------------------------------

def dependency_problems(package_json, lock):
    """E1: every package the repository names (each kind of dependency) at exactly the version of the environment's
    lock; a range, a path or a package the environment does not have is named in a problem."""
    try:
        pkg = json.loads(package_json)
    except ValueError as e:
        return [f"package.json is not JSON ({e})"]
    if not isinstance(pkg, dict):
        return ["package.json is not a JSON object"]
    locked = lock.get("packages") or {}
    problems = []
    for kind in DEP_KINDS:
        deps = pkg.get(kind, {})
        if not isinstance(deps, dict):
            problems.append(f"package.json {kind} is not an object")
            continue
        for name, version in sorted(deps.items()):
            want = (locked.get(f"node_modules/{name}") or {}).get("version")
            if version != want:                        # a range or a path is never the locked version
                problems.append(f"{kind} {name} {version!r} is not in environment {ENVIRONMENT}'s lock "
                                f"({'locked ' + want if want else 'not there'}); a new package is a new environment")
    return problems


def artifact_problems(dist, sw_sha256):
    """A4 and A3 for a built dist, read without following links: [] when it may be published."""
    problems, count, total = [], 0, 0
    found = set()

    def walk(fd, rel):
        nonlocal count, total
        for name in sorted(os.listdir(fd)):
            path = f"{rel}{name}"
            if not SEGMENT.match(name) or name.startswith("."):
                problems.append(f"{path}: a name outside [A-Za-z0-9._-] or starting with a dot")
                continue
            if path.count("/") >= MAX_DEPTH:
                problems.append(f"{path}: deeper than {MAX_DEPTH}")
                continue
            st = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if stat.S_ISDIR(st.st_mode):
                sub = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                try:
                    walk(sub, path + "/")
                finally:
                    os.close(sub)
                continue
            if not stat.S_ISREG(st.st_mode):
                problems.append(f"{path}: not a regular file (a link, device, fifo or socket)")
                continue
            if st.st_nlink > 1:
                problems.append(f"{path}: a hard link")
                continue
            count, total = count + 1, total + st.st_size
            found.add(path)
            ext = os.path.splitext(name)[1]
            if ext not in TYPES:
                problems.append(f"{path}: extension {ext or '(none)'} is not allowed")
                continue
            if st.st_size > MAX_FILE:
                problems.append(f"{path}: {st.st_size} bytes, over {MAX_FILE}")
                continue
            ffd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
            with os.fdopen(ffd, "rb") as f:
                data = f.read(MAX_FILE + 1)
            if ext in TEXT:
                try:
                    data.decode("utf-8")
                except UnicodeDecodeError:
                    problems.append(f"{path}: not valid UTF-8")
            elif not data.startswith(MAGIC[ext]):
                problems.append(f"{path}: its content is not {ext[1:].upper()}")
            if sd.KEY.search(data):
                problems.append(f"{path}: something like a key")
            m = STORAGE.search(data)
            if m and path != "sw.js":
                problems.append(f"{path}: uses browser storage ({m.group().decode()}); API data is never kept in the "
                                "browser")
            if path == "sw.js" and hashlib.sha256(data).hexdigest() != sw_sha256:
                problems.append("sw.js is not the reviewed service worker" + ("" if sw_sha256 else
                                                                              " (none is pinned yet: SW_SHA256)"))

    fd = os.open(dist, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        walk(fd, "")
    finally:
        os.close(fd)
    if count > MAX_FILES:
        problems.append(f"{count} files, over {MAX_FILES}")
    if total > MAX_TOTAL:
        problems.append(f"{total} bytes in total, over {MAX_TOTAL}")
    problems += [f"{p} is missing" for p in ("index.html", "sw.js") if p not in found]
    return problems


# ---- S1: the build -------------------------------------------------------------------------------------------------

def build_image(cfg):
    image, problem = rj.environment_pin(cfg, ENVIRONMENT)
    if problem:
        raise Refused(f"the build environment cannot be used: {problem}")
    return image


def vite_build(src, out, image, *, timeout_s=BUILD_TIMEOUT_S):
    """`vite build` of the read-only workspace `src` into `out` in the environment's image: no network, read-only root,
    no capabilities, this user's uid, limits; out is the only writable mount. -> {exit_code, output}."""
    name = BUILD_PREFIX + secrets.token_hex(6)
    argv = ["docker", "run", "--rm", "--name", name, "--label", "argus.staging.viewer.build=1", "--network", "none",
            "--read-only", "--tmpfs", "/tmp:rw,size=64m,mode=1777", "--user", f"{os.getuid()}:{os.getgid()}",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges", *BUILD_LIMITS,
            "-v", f"{src}:/workspace:ro", "-v", f"{out}:/out", "-w", "/workspace",
            "-e", "NO_COLOR=1", "-e", "HOME=/tmp", image, *BUILD_ARGV]
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=30)
        return {"exit_code": None, "output": f"the build timed out after {timeout_s}s"}
    return {"exit_code": r.returncode, "output": (r.stdout + r.stderr)[-2000:]}


# ---- the viewer's staging area -------------------------------------------------------------------------------------

class Viewer:
    def __init__(self, base=None, ledger=None, sw_sha256=SW_SHA256):
        self.ledger = ledger or sg.Staging()
        self.base = Path(base) if base is not None else self.ledger.base / "apps" / "viewer"
        self.sw_sha256 = sw_sha256
        self.state_path, self.log_path = self.base / "state.json", self.base / "releases.jsonl"

    def state(self):
        try:
            if not os.path.lexists(self.state_path):
                return {"live": None, "history": []}
            s = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            s = None
        if isinstance(s, dict) and isinstance(s.get("history"), list) and \
                all(isinstance(r, str) for r in s["history"]) and \
                (s.get("live") is None or (s["history"] and s["live"] == s["history"][-1])):
            return s
        raise Refused(f"{self.state_path} is unreadable; nothing was changed: restore it by hand (releases.jsonl)")

    def _save(self, state):
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self.state_path)

    def note(self, event, **detail):
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "event": event, **detail})
                    + "\n")

    def releases(self):
        return {e["release"]: e for e in sg._jsonl(self.log_path)
                if e.get("event") == "built" and isinstance(e.get("release"), str)}

    @contextmanager
    def lock(self):
        self.base.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.base / ".lock", os.O_RDWR | os.O_CREAT, 0o600)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise Refused("another viewer command is running; nothing was changed") from None
            yield
        finally:
            os.close(fd)

    def dir(self, release):
        if not sg.RELEASE.match(release):
            raise Refused(f"{release!r} is not a release name")
        return self.base / "releases" / release

    def published(self):
        """The release `current` points to, or None."""
        try:
            m = CURRENT.match(os.readlink(self.base / "current"))
        except OSError:
            return None
        return m.group(1) if m else None

    def reconcile(self):
        """`current` back on the release state.json records live: a command killed between the swap and the record
        leaves them apart, and state.json (with its history) is what rollback goes by."""
        live = self.state()["live"]
        if self.published() == live and (live is not None or not os.path.lexists(self.base / "current")):
            return
        if live is None:
            os.unlink(self.base / "current")
        else:
            self.verify(live)
            _swap(self.base, f"releases/{live}")
        self.note("reconciled", release=live)

    def verify(self, release):
        """The built record of a release whose dist is still file for file what was built, or Refused."""
        rec = self.releases().get(release)
        if rec is None:
            raise Refused(f"release {release} is not one that was built")
        try:
            same = digest(snapshot(self.dir(release))) == rec["dist_digest"]
        except OSError:
            same = False
        if not same:
            raise Refused(f"release {release} changed since its build; nothing was changed")
        return rec

    def publish_dist(self, dist, release, meta):
        """A4/A3-check a built dist, record it as `release` (read-only), then make it live through switch()."""
        problems = artifact_problems(dist, self.sw_sha256)
        if problems:
            raise Refused(f"the build of {release} was not published: " + "; ".join(problems[:8])
                          + (f" (and {len(problems) - 8} more)" if len(problems) > 8 else ""))
        d = self.dir(release)
        if release in self.releases():
            raise Refused(f"release {release} was built already")
        if os.path.lexists(d):                         # left by a publish that stopped before its record
            sd._remove(d)
        d.parent.mkdir(parents=True, exist_ok=True)
        os.rename(dist, d)
        sg._read_only(d)
        files = snapshot(d)
        self.note("built", release=release, **meta, files=files, dist_digest=digest(files),
                  sw_sha256=self.sw_sha256)
        self.switch(release, "deploy", lambda state: {"live": release,
                                                      "history": [r for r in state["history"] if r != release]
                                                      + [release]})
        return release

    def switch(self, release, why, new_state):
        """Smoke-test `release` through a proxy of its own (an ephemeral port on 127.0.0.1), then swap `current` to it
        and record it live. Any failure before the record leaves `current` and state.json as they were."""
        self.verify(release)
        problems = artifact_problems(self.dir(release), self.sw_sha256)
        if problems:                                   # e.g. built before SW_SHA256 named another sw.js
            raise Refused(f"release {release} is not published again: " + "; ".join(problems[:8]))
        state = self.state()
        srv = make_server(self, port=0, release=release)
        t = threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        t.start()
        try:
            results = smoke(self, srv.server_address[1], release=release, listeners=None)
        finally:
            srv.shutdown()
            srv.server_close()
        ok = all(r[1] for r in results)
        self.note("smoke", release=release, ok=ok, results=[list(r) for r in results], why=why)
        if not ok:
            raise Refused(f"release {release} failed its smoke test ("
                          + "; ".join(f"{c}: {d}" for c, k, d in results if not k)
                          + f"); {state['live'] or 'nothing'} is still live")
        old = os.readlink(self.base / "current") if os.path.islink(self.base / "current") else None
        _swap(self.base, f"releases/{release}")
        try:
            self._save(new_state(state))
        except BaseException:
            if old is None:
                os.unlink(self.base / "current")
            else:
                _swap(self.base, old)
            raise
        try:
            self.note("live", release=release, by=why)
        except OSError:
            pass                                       # state.json and `current` agree: it is live
        return results


def _swap(base, target):
    link = base / f".current-{os.getpid()}"
    if os.path.lexists(link):
        os.unlink(link)
    os.symlink(target, link)
    os.replace(link, base / "current")


# ---- commands ------------------------------------------------------------------------------------------------------

def deploy(job_id, *, cfg, deps, jobs_dir=rj.JOBS, viewer=None):
    v = viewer or Viewer()
    job = rj.open_job(job_id, jobs_dir)
    image = build_image(cfg)
    with v.lock():
        commit, repo = sg.reviewed_commit(job)
        if job.data["inputs"].get("environment") != ENVIRONMENT:
            raise Refused(f"job {job.id} ran in environment {job.data['inputs'].get('environment')!r}, not "
                          f"{ENVIRONMENT}: it is not a viewer job")
        release = sg.release_name(job, commit)
        v.reconcile()
        state = v.state()
        if state["live"] == release:
            raise Refused(f"release {release} is already live")
        known = v.releases().get(release)
        if known is not None and known.get("image") != image:
            raise Refused(f"release {release} was built on image {str(known.get('image'))[:19]}, and {ENVIRONMENT} "
                          f"is {image[:19]} now; nothing was changed")
        sg._confirm(deps, "\n".join([
            f"== staging viewer deploy (job {job.id}) ==",
            f"release {release}: {repo} at {commit[:12]} (applied as reviewed)",
            f"build: vite build in {ENVIRONMENT} {image[:19]}, no network, read-only archive"
            + (" (built already: checked again)" if known else ""),
            f"published at {v.base / 'current'}, served by the proxy on {BIND}:{PORT}",
            f"live now: {state['live'] or 'nothing'}; rollback after this: {state['live'] or 'none'}",
            "staging only: argus-ledger's release is not touched"]))
        if known is not None:
            v.switch(release, "deploy", lambda s: {"live": release,
                                                   "history": [r for r in s["history"] if r != release] + [release]})
        else:
            v.base.mkdir(parents=True, exist_ok=True)
            tmp = v.base / f".build-{os.getpid()}-{secrets.token_hex(4)}"
            tmp.mkdir(mode=0o700)
            try:
                archive = sg.unpack(repo, commit, tmp / "src")
                try:
                    package = (tmp / "src" / "package.json").read_bytes()
                except OSError:
                    package = None
                problems = (dependency_problems(package, json.loads(LOCK_FILE.read_text(encoding="utf-8")))
                            if package is not None else ["the commit has no package.json"])
                problems += va.vitest_workspace_problems(tmp / "src")
                if problems:
                    raise Refused(f"commit {commit[:12]} is not built: " + "; ".join(problems[:5]))
                (tmp / "out").mkdir(mode=0o700)
                r = vite_build(tmp / "src", tmp / "out", image)
                if r["exit_code"] != 0:
                    raise Refused(f"vite build failed (exit {r['exit_code']}): {r['output'][-600:]}")
                v.publish_dist(tmp / "out", release, {"job": job.id, "repo": repo, "commit": commit, "image": image,
                                                      "environment": ENVIRONMENT, "archive_sha256": sg._sha(archive)})
            finally:
                if os.path.lexists(tmp):
                    sd._remove(tmp)
    with job.lock():
        job.note(deps, "staged", release=release, app="viewer")
    return release


def rollback(*, deps, viewer=None):
    v = viewer or Viewer()
    with v.lock():
        v.reconcile()
        state = v.state()
        if not state["live"] or len(state["history"]) < 2:
            raise Refused("there is no earlier viewer release to roll back to")
        current, previous = state["history"][-1], state["history"][-2]
        v.verify(previous)
        sg._confirm(deps, "\n".join(["== staging viewer rollback ==", f"live now: {current}",
                                     f"publish again: {previous}", "argus-ledger's release is not touched"]))
        v.switch(previous, "rollback", lambda s: {"live": previous, "history": s["history"][:-1]})
    return previous


def status(viewer=None):
    v = viewer or Viewer()
    try:
        state = v.state()
    except Refused as e:
        return f"{STATE_PROBLEM}{e}"
    rels, live = v.releases(), state["live"]
    lines = [f"viewer live: {live or 'nothing'}" + (f" (current -> {v.published()})" if v.published() != live else "")]
    if live in rels:
        lines.append(f"  job {rels[live].get('job')}, commit {str(rels[live].get('commit'))[:12]}, image "
                     f"{str(rels[live].get('image'))[:19]}")
    prev = state["history"][-2] if len(state["history"]) >= 2 else None
    lines.append(f"viewer rollback would publish: {prev or 'nothing (no earlier release)'}")
    lines.append(f"proxy: {BIND}:{PORT}" + ("" if v.sw_sha256 else "; no reviewed sw.js pinned (no release is published)"))
    return "\n".join(lines)


# ---- S2: the proxy -------------------------------------------------------------------------------------------------

class Server(http.server.ThreadingHTTPServer):
    daemon_threads = True


def make_server(viewer, port=PORT, release=None):
    """The proxy on BIND:port (0: an ephemeral port, for a release's own smoke test). `release`: serve that release's
    files instead of `current`'s."""
    srv = Server((BIND, port), Handler)
    srv.viewer, srv.release, srv.peer = viewer, release, None   # peer: (ledger release, its container's pid)
    return srv


class Handler(http.server.BaseHTTPRequestHandler):
    timeout = 10
    server_version, sys_version = "argus-staging", ""

    def log_message(self, fmt, *args):
        pass

    def __getattr__(self, name):                       # every method but GET and HEAD
        if name.startswith("do_"):
            return self._refuse
        raise AttributeError(name)

    def _send(self, status, body=b"", ctype="application/json", api=False):
        self.close_connection = True
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store" if api else "no-cache")
        for k, val in SECURITY.items():
            self.send_header(k, val)
        self.send_header("Connection", "close")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def send_error(self, code, message=None, explain=None):   # a request http.server could not parse
        self._error(code, message or "bad request")

    def _error(self, status, why):
        self._send(status, json.dumps({"error": why}).encode(), api=True)

    def _host_ok(self):
        port = self.server.server_address[1]
        hosts = self.headers.get_all("Host") or []
        return len(hosts) == 1 and hosts[0] in (f"localhost:{port}", f"127.0.0.1:{port}")

    def _refuse(self):
        if not self._host_ok():
            return self._error(421, "misdirected request")
        self._error(405, "only GET and HEAD")

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        if not self._host_ok():
            return self._error(421, "misdirected request")
        path = self.path
        if path == "/api" or path.startswith(("/api/", "/api?")):
            m = API.match(path)
            return self._api(f"/{m.group(1)}") if m else self._error(404, "not found")
        return self._file(path.split("?", 1)[0])

    def _api(self, upstream):
        ledger = self.server.viewer.ledger
        try:
            live = ledger.state()["live"]
        except rj.Refused:
            live = None
        if not live:
            return self._error(503, "argus-ledger is not live")
        cached = self.server.peer
        from_cache = bool(cached) and cached[0] == live
        peer = cached[1] if from_cache else ledger.container_pid(live)
        if peer is None:
            return self._error(503, "argus-ledger is not live")
        try:
            conn = http.client.HTTPConnection("localhost", timeout=10)
            try:
                conn.sock = sg._connect(ledger.dir(live) / "sock" / "app.sock", peer=peer)
            except OSError:
                if not from_cache:
                    raise
                peer = ledger.container_pid(live)     # the container was restarted: ask docker once more
                if peer is None:
                    raise
                conn.sock = sg._connect(ledger.dir(live) / "sock" / "app.sock", peer=peer)
            self.server.peer = (live, peer)
            try:
                conn.putrequest("GET", upstream, skip_host=True, skip_accept_encoding=True)
                conn.putheader("Host", sg.HOST)
                conn.putheader("Connection", "close")
                conn.endheaders()
                r = conn.getresponse()
                body = r.read(MAX_ANSWER + 1)
                status, ctype = r.status, r.getheader("Content-Type") or ""
            finally:
                conn.close()
            json.loads(body)
        except (OSError, ValueError, http.client.HTTPException):
            return self._error(502, "argus-ledger did not answer with JSON")
        if status not in (200, 404) or not ctype.startswith("application/json") or len(body) > MAX_ANSWER:
            return self._error(502, "argus-ledger did not answer with JSON")
        self._send(status, body, api=True)

    def _root(self):
        v = self.server.viewer
        release = self.server.release or v.published()
        if release is None or not sg.RELEASE.match(release):
            return None
        try:
            rfd = os.open(v.base / "releases", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        except OSError:
            return None
        try:
            return os.open(release, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=rfd)
        except OSError:
            return None
        finally:
            os.close(rfd)

    def _file(self, raw):
        try:
            path = unquote(raw, errors="strict")
        except UnicodeDecodeError:
            path = ""
        route = path.endswith("/") and path != "/"     # /jobs/: an app route
        body = path[1:-1] if route else path[1:]
        segments = body.split("/") if body else ["index.html"]
        if not path.startswith("/") or len(segments) > MAX_DEPTH or \
                not all(SEGMENT.match(s) and not s.startswith(".") for s in segments):
            return self._error(404, "not found")
        root = self._root()
        if root is None:
            return self._error(503, "no viewer release is published")
        try:
            got = _read(root, segments)
            if got is None and (route or "." not in segments[-1]):
                got = _read(root, ["index.html"])          # an app route
        finally:
            os.close(root)
        if got is None:
            return self._error(404, "not found")
        name, data = got
        self._send(200, data, TYPES.get(os.path.splitext(name)[1], "application/octet-stream"))


def _read(root, segments):
    """(name, bytes) of a regular file below the directory fd `root`, every step opened without following a link; None
    when it is missing (or a link, or not a regular file)."""
    fds = []
    try:
        fd = root
        for s in segments[:-1]:
            fd = os.open(s, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            fds.append(fd)
        ffd = os.open(segments[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        with os.fdopen(ffd, "rb") as f:
            if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):
                return None
            return segments[-1], f.read(MAX_FILE + 1)
    except OSError:
        return None
    finally:
        for fd in fds:
            os.close(fd)


def serve():
    """`argus stage proxy`: forever, on 127.0.0.1:8710 only."""
    srv = make_server(Viewer())
    try:
        srv.serve_forever()
    finally:
        srv.server_close()


# ---- S3, A5: the smoke test ----------------------------------------------------------------------------------------

def listeners(port):
    """The local addresses listening on TCP `port` (ss -ltnH), or None when ss failed."""
    try:
        r = subprocess.run(["ss", "-ltnH", f"sport = :{port}"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode:
        return None
    return [line.split()[3] for line in r.stdout.splitlines() if len(line.split()) >= 4]


def _ask(port, method, path, host=None):
    conn = http.client.HTTPConnection(BIND, port, timeout=10)
    try:
        conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
        conn.putheader("Host", host or f"localhost:{port}")
        conn.endheaders()
        r = conn.getresponse()
        return r.status, {k.lower(): val for k, val in r.getheaders()}, r.read(MAX_FILE + 1)
    finally:
        conn.close()


def smoke(viewer, port, *, release=None, listeners=listeners, held=False):
    """[(check, ok, detail)] of S3 against the proxy on 127.0.0.1:port serving `release` (default: the live one). The
    summary is compared with the active snapshot under the data lock (`held`: the caller holds it). `listeners` None
    leaves out A5's listener check (a release's own smoke test on an ephemeral port)."""
    release = release or viewer.state()["live"]
    rec = viewer.releases().get(release) if release else None
    if rec is None:
        return [("GET / -> 200 index.html of the release", False, f"release {release} is not one that was built")]
    files, out = rec.get("files") or {}, []

    def check(name, fn):
        try:
            ok, detail = fn()
        except Exception as e:                         # noqa: BLE001  (any failure is a failed check, with its type)
            ok, detail = False, f"{type(e).__name__}: {str(e)[:120]}"
        out.append((name, bool(ok), detail))

    index = []

    def root():
        status, _, body = _ask(port, "GET", "/")
        index.append(body)
        return status == 200 and sg._sha(body) == files.get("index.html"), f"{status} {sg._sha(body)[:12]}"
    check("GET / -> 200 index.html of the release", root)
    for ref in sorted(set(REFS.findall(index[0] if index else b""))):
        ref = ref.decode("utf-8", "replace")
        if ":" in ref or ref.startswith("//") or os.path.splitext(ref)[1] not in TYPES:
            continue                                   # another site, a data: URL, or an app route (/jobs/)
        ref = posixpath.normpath("/" + ref.removeprefix("./").lstrip("/"))

        def asset(ref=ref):
            status, _, body = _ask(port, "GET", ref)
            return status == 200 and sg._sha(body) == files.get(ref.lstrip("/")), f"{status} {sg._sha(body)[:12]}"
        check(f"GET {ref} -> 200 as recorded", asset)

    def summary():
        with (sd._nothing() if held else sd.refresh_lock(viewer.ledger.data, wait_s=sd.LOCK_WAIT_S)):
            man = sd.manifest(viewer.ledger.data)
            status, headers, body = _ask(port, "GET", "/api/summary")
        got = json.loads(body) if status == 200 else {}
        ok = man is not None and headers.get("cache-control") == "no-store" and \
            {k: got.get(k) for k in ("jobs", "cost_nano", "skipped")} == \
            {"jobs": len(man["jobs"]), "cost_nano": man["cost_nano"], "skipped": 0}
        return ok, f"{status} {headers.get('cache-control')} {body[:120]!r}"
    check("GET /api/summary -> 200 the snapshot's numbers, no-store", summary)
    for name, method, path, host, want in (
            ("Host evil.example -> 421", "GET", "/", "evil.example", 421),
            ("POST / -> 405", "POST", "/", None, 405),
            ("GET /../x -> 404", "GET", "/../x", None, 404),
            ("GET /api/x -> 404", "GET", "/api/x", None, 404)):
        check(name, lambda m=method, p=path, h=host, w=want: (lambda s: (s == w, str(s)))(_ask(port, m, p, h)[0]))
    if listeners is not None:
        def only():
            got = listeners(port)
            return got == [f"{BIND}:{port}"], f"listening: {got}"
        check(f"listen {BIND}:{port} only", only)
    return out

