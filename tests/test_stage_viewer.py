"""SPEC_PWA_VIEWER S and §8 (PR 2): the viewer's release is a static build of an applied commit, made without network
and checked before it is published by an atomic swap; the proxy listens only on 127.0.0.1:8710, answers GET/HEAD for a
checked Host, forwards three API paths to the live argus-ledger release with headers of its own, and serves files of the
published release only. The docker tests need the checked pwa_node22 image; without it they are skipped with "SANDBOX NOT
AVAILABLE", which scripts/verify.sh does not count as passing."""
import hashlib
import http.client
import http.server
import json
import os
import shutil
import socket
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from router import job as rj  # noqa: E402
from router import stage as sg  # noqa: E402
from router import stage_data as sd  # noqa: E402
from router import stage_viewer as sv  # noqa: E402
from runner import load_config  # noqa: E402
from test_stage import Said, UnixHTTP, applied_job, git, with_fixture  # noqa: E402

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="Unix sockets and docker on the VM")

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "fixtures" / "repos" / "viewer_demo"
SW = (DEMO / "public" / "sw.js").read_bytes()
SW_SHA = hashlib.sha256(SW).hexdigest()
LOCK = json.loads((ROOT / "environments" / "pwa_node22" / "package-lock.json").read_text())
LEDGER_RELEASE = "jledger-0123456789ab"
JS = b"import{a as b}from'x';console.log('viewer');\n"
INDEX = (b'<!doctype html><html><head><link rel="manifest" href="/manifest.webmanifest">'
         b'<script type="module" crossorigin src="/assets/index-abc123.js"></script></head>'
         b'<body><div id="root"></div></body></html>\n')
PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 32


def make_dist(d, **files):
    """A dist as vite builds it; `files` adds (bytes) or removes (None) entries."""
    want = {"index.html": INDEX, "assets/index-abc123.js": JS, "sw.js": SW, "icon.png": PNG,
            "manifest.webmanifest": b'{"name": "viewer"}\n', **files}
    for rel, data in want.items():
        if data is not None:
            (d / rel).parent.mkdir(parents=True, exist_ok=True)
            (d / rel).write_bytes(data)
    return d


# ---- A4: the artifact --------------------------------------------------------------------------------------------------

def test_a_dist_as_vite_builds_it_passes(tmp_path):
    assert sv.artifact_problems(make_dist(tmp_path), SW_SHA) == []


@pytest.mark.parametrize("files, problem", [
    ({"index.html": None}, "index.html"),
    ({"app.js.map": b"{}"}, "app.js.map"),                                  # extension outside the allowlist
    ({"run.sh": b"echo"}, "run.sh"),
    ({"noext": b"x"}, "noext"),
    ({".env": b"A=1"}, ".env"),                                             # a segment starting with a dot
    ({"assets/.hidden/a.js": b"1"}, ".hidden"),
    ({"a b.js": b"1"}, "a b.js"),                                           # a character outside [A-Za-z0-9._-]
    ({"a/b/c/d/e.js": b"1"}, "a/b/c/d/e.js"),                               # deeper than 4
    ({"bad.html": b"\xff\xfe<html>"}, "bad.html"),                          # not UTF-8
    ({"bad.js": b"\xc3\x28"}, "bad.js"),
    ({"bad.json": b"\xff"}, "bad.json"),
    ({"fake.png": b"GIF89a" + b"\0" * 10}, "fake.png"),                     # content is not the type
    ({"fake.ico": b"\x89PNG\r\n\x1a\n"}, "fake.ico"),
    ({"big.js": b"/" * (2 * 1024 * 1024 + 1)}, "big.js"),                  # a file over 2 MB
    ({"k.js": b'const k="sk-ant-api03-abcdefghijklmnop"'}, "k.js"),         # a key pattern
    ({"assets/index-abc123.js": JS + b"localStorage.setItem('a',1)"}, "localStorage"),
    ({"assets/index-abc123.js": JS + b"window.sessionStorage"}, "sessionStorage"),
    ({"assets/index-abc123.js": JS + b"indexedDB.open('x')"}, "indexedDB"),
    ({"assets/index-abc123.js": JS + b"caches.open('x')"}, "caches."),
    ({"assets/index-abc123.js": JS + b"x instanceof CacheStorage"}, "CacheStorage"),
    ({"other.html": b"<script>localStorage.x=1</script>"}, "localStorage"),
    ({"sw.js": None}, "sw.js"),
    ({"sw.js": SW + b"\n// changed\n"}, "sw.js"),                           # not the reviewed service worker
])
def test_a_dist_that_breaks_a_rule_is_refused(tmp_path, files, problem):
    got = sv.artifact_problems(make_dist(tmp_path, **files), SW_SHA)
    assert got and any(problem in p for p in got), got


def test_the_reviewed_service_worker_may_use_the_cache_api(tmp_path):
    assert b"caches." in SW
    assert sv.artifact_problems(make_dist(tmp_path), SW_SHA) == []


def test_without_a_reviewed_service_worker_every_release_is_refused(tmp_path):
    assert sv.SW_SHA256 is None or len(sv.SW_SHA256) == 64
    got = sv.artifact_problems(make_dist(tmp_path), None)
    assert got and any("sw.js" in p for p in got), got


@pytest.mark.parametrize("make, problem", [
    (lambda d: os.symlink("index.html", d / "link.html"), "link.html"),
    (lambda d: os.symlink("/etc", d / "assets" / "etc"), "etc"),
    (lambda d: os.link(d / "index.html", d / "hard.html"), "hard.html"),
    (lambda d: os.mkfifo(d / "pipe.txt"), "pipe.txt"),
])
def test_links_and_special_files_are_refused_without_following_them(tmp_path, make, problem):
    d = make_dist(tmp_path)
    make(d)
    got = sv.artifact_problems(d, SW_SHA)
    assert got and any(problem in p for p in got), got


def test_a_socket_in_the_dist_is_refused(tmp_path):
    d = make_dist(tmp_path)
    dfd = os.open(d, os.O_RDONLY | os.O_DIRECTORY)
    s = socket.socket(socket.AF_UNIX)
    try:
        s.bind(f"/proc/self/fd/{dfd}/sock.txt")
        got = sv.artifact_problems(d, SW_SHA)
    finally:
        s.close()
        os.close(dfd)
    assert got and any("sock.txt" in p for p in got), got


def test_too_many_files_or_too_much_in_total_is_refused(tmp_path):
    many = make_dist(tmp_path / "many", **{f"a{i}.txt": b"x" for i in range(200)})
    assert any("files" in p for p in sv.artifact_problems(many, SW_SHA))
    big = make_dist(tmp_path / "big", **{f"b{i}.js": b"/" * (1024 * 1024 + 1) for i in range(5)})
    assert any("total" in p for p in sv.artifact_problems(big, SW_SHA))
    one_more = make_dist(tmp_path / "one_more", **{f"d{i}.txt": b"x" for i in range(200 - 5 + 1)})
    assert any("201 files" in p for p in sv.artifact_problems(one_more, SW_SHA))
    exact = make_dist(tmp_path / "exact", **{f"c{i}.txt": b"x" for i in range(200 - 5)})
    assert sv.artifact_problems(exact, SW_SHA) == []


# ---- E1: the repository's packages ---------------------------------------------------------------------------------

def pkg(**kinds):
    return json.dumps({"name": "v", **kinds}).encode()


def test_packages_that_are_a_subset_of_the_lock_pass():
    assert sv.dependency_problems((DEMO / "package.json").read_bytes(), LOCK) == []
    assert sv.dependency_problems(pkg(), LOCK) == []


@pytest.mark.parametrize("package, problem", [
    (pkg(dependencies={"react": "19.1.1"}), "react"),                       # another version
    (pkg(dependencies={"react": "^19.1.0"}), "react"),                      # a range, not the version
    (pkg(devDependencies={"left-pad": "1.3.0"}), "left-pad"),               # not in the environment
    (pkg(peerDependencies={"lodash": "4.17.21"}), "lodash"),
    (pkg(optionalDependencies={"sharp": "0.33.5"}), "sharp"),
    (pkg(dependencies={"react": "file:../react"}), "react"),
    (pkg(dependencies=["react"]), "dependencies"),
    (b"not json", "package.json"),
    (json.dumps(["x"]).encode(), "package.json"),
])
def test_packages_outside_the_lock_are_refused_by_name(package, problem):
    got = sv.dependency_problems(package, LOCK)
    assert got and any(problem in p for p in got), got


# ---- S2, A1, A2, A5: the proxy -------------------------------------------------------------------------------------

def test_the_proxy_is_bound_to_127_0_0_1_on_8710_and_never_8000():
    assert (sv.BIND, sv.PORT) == ("127.0.0.1", 8710)
    assert sv.PORT != 8000


POLL_S = 0.02


def serve(path, answers, requests):
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append((self.command, self.path, list(self.headers.items())))
            status, body = answers(self.headers.get("Host"), self.path)
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

        def address_string(self):
            return "unix"
    dfd = os.open(Path(path).parent, os.O_RDONLY | os.O_DIRECTORY)
    try:                                   # bound through the directory's fd: tmp paths pass the 107-byte limit
        srv = UnixHTTP(f"/proc/self/fd/{dfd}/{Path(path).name}", H)
    finally:
        os.close(dfd)
    threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": POLL_S}, daemon=True).start()
    return srv


def start(srv):
    threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": POLL_S}, daemon=True).start()
    return srv


class Upstream:
    """A stand-in for the live argus-ledger release: its socket in the release's directory, every request recorded."""

    def __init__(self, st, man, answers=None):
        self.requests = []
        sock = st.dir(LEDGER_RELEASE) / "sock"
        sock.mkdir(parents=True)
        summary = {"jobs": len(man["jobs"]), "cost_nano": man["cost_nano"], "cost_usd": "0", "skipped": 0}

        def answer(host, path):
            if answers:
                return answers(host, path)
            if host != sg.HOST:
                return 400, b"Invalid host header"
            if path == "/summary":
                return 200, json.dumps(summary).encode()
            if path == "/jobs":
                return 200, json.dumps([{"job": j} for j in man["jobs"]]).encode()
            if path.startswith("/jobs/") and path[6:] in man["jobs"]:
                return 200, json.dumps({"job": path[6:]}).encode()
            return 404, b'{"detail": "Not Found"}'

        self.srv = serve(sock / "app.sock", answer, self.requests)

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    st = with_fixture(sg.Staging(tmp_path / "staging", run=lambda *a, **k: (1, "", "no docker in this test")))
    st._save({"live": LEDGER_RELEASE, "history": [LEDGER_RELEASE]})
    monkeypatch.setattr(sg.Staging, "container_pid", lambda self, release: os.getpid() if release == LEDGER_RELEASE
                        else None)
    up = Upstream(st, sd.manifest(st.data))
    st.upstream = up
    yield st
    up.close()


def publish(viewer, name="jviewer-aaaaaaaaaaaa", **files):
    """A release published as deploy publishes one (dist checked, read-only, `current` swapped), without docker."""
    d = make_dist(Path(viewer.base) / "build-input" / name, **files)
    return viewer.publish_dist(d, name, {"job": name.split("-")[0], "commit": name.split("-")[1] * 3 + "0000",
                                         "image": "sha256:" + "1" * 64})


@pytest.fixture
def viewer(tmp_path, ledger, monkeypatch):
    """A published release. Its own smoke test is left out here, so that a broken proxy fails the proxy's tests rather
    than this fixture (the smoke test as a gate has tests of its own)."""
    v = sv.Viewer(tmp_path / "staging" / "apps" / "viewer", ledger=ledger, sw_sha256=SW_SHA)
    with monkeypatch.context() as m:
        m.setattr(sv, "smoke", lambda *a, **k: [("left out", True, "")])
        publish(v)
    return v


@pytest.fixture
def proxy(viewer):
    srv = sv.make_server(viewer, port=0)
    start(srv)
    viewer.ledger.upstream.requests.clear()             # the publish's own smoke test asked for /api/summary
    yield srv
    srv.shutdown()
    srv.server_close()


def request(srv, method, path, host=None, headers=(), body=None):
    """One raw request (the path is sent as it is, never normalised by a client library)."""
    port = srv.server_address[1]
    lines = [f"{method} {path} HTTP/1.1", f"Host: {host or f'localhost:{port}'}", "Connection: close", *headers]
    if body is not None:
        lines.append(f"Content-Length: {len(body)}")
    s = socket.create_connection(("127.0.0.1", port), timeout=10)
    s.sendall(("\r\n".join(lines) + "\r\n\r\n").encode() + (body or b""))
    r = http.client.HTTPResponse(s, method=method)
    r.begin()
    out = r.status, {k.lower(): v for k, v in r.getheaders()}, r.read()
    s.close()
    return out


def test_the_server_listens_on_127_0_0_1_only(proxy):
    assert proxy.server_address[0] == "127.0.0.1"


@pytest.mark.parametrize("host, status", [
    ("localhost:{port}", 200), ("127.0.0.1:{port}", 200),
    ("evil.example", 421), ("evil.example:{port}", 421), ("localhost", 421), ("127.0.0.1", 421),
    ("localhost:1", 421), ("[::1]:{port}", 421), ("LOCALHOST:{port}x", 421),
])
def test_only_a_local_host_header_is_answered(proxy, host, status):
    port = proxy.server_address[1]
    for path in ("/", "/api/summary"):
        got, headers, _ = request(proxy, "GET", path, host=host.format(port=port))
        assert got == status, (path, host, got)


def test_a_request_http_server_cannot_parse_still_carries_the_security_headers(proxy):
    s = socket.create_connection(("127.0.0.1", proxy.server_address[1]), timeout=10)
    s.sendall(b"GET /" + b"a" * 70000 + b" HTTP/1.1\r\n\r\n")
    r = http.client.HTTPResponse(s, method="GET")
    r.begin()
    assert r.status == 414 and {k.lower(): v for k, v in r.getheaders() if k.lower() in SECURITY} == SECURITY
    s.close()


def test_a_state_that_cannot_be_saved_leaves_current_where_it_was(viewer, monkeypatch):
    live, link = viewer.state()["live"], os.readlink(viewer.base / "current")
    monkeypatch.setattr(sv.Viewer, "_save", lambda self, state: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(OSError):
        publish(viewer, "jnew-cccccccccccc")
    assert viewer.state()["live"] == live and os.readlink(viewer.base / "current") == link


def test_two_host_headers_are_refused(proxy):
    got, _, _ = request(proxy, "GET", "/", headers=["Host: evil.example"])
    assert got == 421


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "PATCH", "OPTIONS", "TRACE", "CONNECT"])
def test_only_get_and_head_are_answered(proxy, method):
    for path in ("/", "/api/summary", "/index.html"):
        got, _, _ = request(proxy, method, path, body=b"{}")
        assert got == 405, (method, path, got)


def test_head_answers_like_get_without_a_body(proxy):
    got, headers, body = request(proxy, "HEAD", "/")
    assert got == 200 and body == b"" and headers["content-type"].startswith("text/html")


SECURITY = {"content-security-policy": "default-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; "
                                       "base-uri 'none'; frame-ancestors 'none'",
            "x-content-type-options": "nosniff", "referrer-policy": "no-referrer"}


@pytest.mark.parametrize("path", ["/", "/assets/index-abc123.js", "/api/summary", "/api/x", "/nope.js"])
def test_every_answer_carries_the_security_headers(proxy, path):
    _, headers, _ = request(proxy, "GET", path)
    assert {k: headers.get(k) for k in SECURITY} == SECURITY, headers


def test_the_three_api_paths_reach_the_live_ledger_without_being_cached(proxy, ledger):
    man = sd.manifest(ledger.data)
    job = man["jobs"][0]
    for path, want in (("/api/summary", "/summary"), ("/api/jobs", "/jobs"), (f"/api/jobs/{job}", f"/jobs/{job}")):
        got, headers, body = request(proxy, "GET", path)
        assert got == 200 and headers["cache-control"] == "no-store", (path, got, headers)
        assert headers["content-type"].startswith("application/json")
        json.loads(body)
        assert ledger.upstream.requests[-1][:2] == ("GET", want)
    got, headers, _ = request(proxy, "GET", "/api/jobs/jnot_there")
    assert got == 404 and headers["cache-control"] == "no-store"


@pytest.mark.parametrize("path", [
    "/api", "/api/", "/api/x", "/api/summary/", "/api/summary?x=1", "/api/jobs?state=DONE", "/api/jobs/",
    "/api/jobs/jabc/x", "/api/jobs/BAD", "/api/jobs/../summary", "/api/jobs/%2e%2e", "/api/jobs/jabc%2fx",
    "/api/jobs/j" + "a" * 41, "/api/jobs.csv", "/api/ui", "/api//summary", "/api/summary%00",
])
def test_any_other_api_path_is_404_and_never_forwarded(proxy, ledger, path):
    got, headers, _ = request(proxy, "GET", path)
    assert got == 404, (path, got)
    assert ledger.upstream.requests == []


def test_client_headers_are_never_forwarded(proxy, ledger):
    request(proxy, "GET", "/api/summary", headers=[
        "X-Forwarded-For: 10.0.0.1", "X-Forwarded-Host: staging.local", "Forwarded: for=10.0.0.1;host=x",
        "X-Real-IP: 10.0.0.1", "Cookie: session=abc", "Authorization: Bearer abc", "User-Agent: phone",
        "Accept: text/html", "X-Anything: 1"])
    (_, _, headers), = ledger.upstream.requests
    names = {k.lower() for k, _ in headers}
    assert dict((k.lower(), v) for k, v in headers)["host"] == sg.HOST
    assert names <= {"host", "connection", "accept-encoding", "content-length"}, headers


def test_an_answer_that_is_not_json_is_not_passed_on(tmp_path, viewer, ledger):
    ledger.upstream.close()
    shutil.rmtree(ledger.dir(LEDGER_RELEASE) / "sock")
    ledger.upstream = Upstream(ledger, sd.manifest(ledger.data),
                               answers=lambda h, p: (200, b"<html><script>alert(1)</script></html>"))
    srv = sv.make_server(viewer, port=0)
    start(srv)
    try:
        got, headers, body = request(srv, "GET", "/api/summary")
    finally:
        srv.shutdown()
        srv.server_close()
    assert got == 502 and b"alert" not in body and headers["cache-control"] == "no-store"


@pytest.mark.parametrize("status", [500, 302, 201, 403])
def test_only_a_200_or_404_answer_is_passed_on(viewer, ledger, status):
    ledger.upstream.close()
    shutil.rmtree(ledger.dir(LEDGER_RELEASE) / "sock")
    ledger.upstream = Upstream(ledger, sd.manifest(ledger.data), answers=lambda h, p: (status, b'{"detail": "x"}'))
    srv = start(sv.make_server(viewer, port=0))
    try:
        got, headers, _ = request(srv, "GET", "/api/summary")
    finally:
        srv.shutdown()
        srv.server_close()
    assert got == 502 and headers["cache-control"] == "no-store"


def test_the_api_is_only_read_from_the_live_releases_container(proxy, ledger, monkeypatch):
    monkeypatch.setattr(sg.Staging, "container_pid", lambda self, release: os.getpid() + 1)
    got, _, _ = request(proxy, "GET", "/api/summary")
    assert got == 502 and ledger.upstream.requests == []


def test_a_link_in_place_of_the_ledger_socket_is_not_followed(tmp_path, proxy, ledger):
    sock = ledger.dir(LEDGER_RELEASE) / "sock" / "app.sock"
    os.rename(sock, sock.with_name("real.sock"))
    os.symlink("real.sock", sock)
    got, _, _ = request(proxy, "GET", "/api/summary")
    assert got == 502 and ledger.upstream.requests == []


def test_nothing_live_in_the_ledger_is_503(proxy, ledger):
    ledger._save({"live": None, "history": [LEDGER_RELEASE]})
    got, headers, _ = request(proxy, "GET", "/api/summary")
    assert got == 503 and headers["cache-control"] == "no-store"


def test_files_come_from_the_published_release(proxy, viewer):
    got, headers, body = request(proxy, "GET", "/")
    assert (got, body) == (200, INDEX) and headers["content-type"] == "text/html; charset=utf-8"
    got, headers, body = request(proxy, "GET", "/assets/index-abc123.js")
    assert (got, body) == (200, JS) and headers["content-type"] == "text/javascript; charset=utf-8"
    got, headers, body = request(proxy, "GET", "/manifest.webmanifest")
    assert got == 200 and headers["content-type"] == "application/manifest+json"
    got, headers, body = request(proxy, "GET", "/icon.png")
    assert (got, body) == (200, PNG) and headers["content-type"] == "image/png"


def test_an_app_route_is_answered_with_index_html(proxy):
    for path in ("/jobs", "/jobs/j20261030_060939_8433", "/settings/"):
        got, headers, body = request(proxy, "GET", path)
        assert (got, body) == (200, INDEX), path
    got, _, _ = request(proxy, "GET", "/assets/missing-123.js")       # a missing file is not the app's page
    assert got == 404


@pytest.mark.parametrize("path", [
    "/../x", "/..", "/%2e%2e/state.json", "/assets/../../state.json", "/%2E%2E%2Fstate.json", "/.lock",
    "/assets/%2fetc%2fpasswd", "//etc/passwd", "/a\\b", "/state.json%00", "x", "/assets/.hidden",
    "/a/b/c/d/e/f", "/releases/x", "/../releases.jsonl", "/%2e%2e/%2e%2e/staging/state.json",
])
def test_a_path_outside_the_release_is_never_read(proxy, viewer, path):
    (Path(viewer.base) / "state.json").write_text('{"live": "SECRET"}')    # what a traversal would reach
    got, _, body = request(proxy, "GET", path)
    assert got == 404 or (got, body) == (200, INDEX), (path, got)          # not there, or an app route
    assert b"SECRET" not in body and b"root:" not in body


def test_a_link_inside_the_release_is_not_followed(tmp_path, ledger):
    v = sv.Viewer(tmp_path / "v", ledger=ledger, sw_sha256=SW_SHA)
    publish(v)
    rel = Path(os.path.realpath(v.base / "current"))
    rel.chmod(0o755)
    (tmp_path / "secret.txt").write_text("secret")
    os.symlink(tmp_path / "secret.txt", rel / "leak.txt")
    os.symlink(tmp_path, rel / "out")
    srv = sv.make_server(v, port=0)
    start(srv)
    try:
        for path in ("/leak.txt", "/out/secret.txt"):
            got, _, body = request(srv, "GET", path)
            assert got == 404 and b"secret" not in body, path
    finally:
        srv.shutdown()
        srv.server_close()


def test_without_a_published_release_files_are_503(tmp_path, ledger):
    v = sv.Viewer(tmp_path / "empty", ledger=ledger, sw_sha256=SW_SHA)
    srv = sv.make_server(v, port=0)
    start(srv)
    try:
        assert request(srv, "GET", "/")[0] == 503
    finally:
        srv.shutdown()
        srv.server_close()


def test_the_proxy_writes_nothing(proxy, viewer, ledger, tmp_path):
    def tree():
        return {str(p): (p.stat().st_mtime_ns, p.stat().st_size) for p in (tmp_path / "staging").rglob("*")
                if not p.is_socket() and not p.is_symlink()}
    before = tree()
    for path in ("/", "/api/summary", "/api/jobs", "/nope", "/../x"):
        request(proxy, "GET", path)
    request(proxy, "POST", "/", body=b"x")
    assert tree() == before


# ---- S3, A5: the smoke test ----------------------------------------------------------------------------------------

def test_the_smoke_test_of_a_good_release_passes(proxy, viewer):
    port = proxy.server_address[1]
    results = sv.smoke(viewer, port, listeners=lambda p: [f"127.0.0.1:{p}"])
    assert [r for r in results if not r[1]] == [], results
    names = " ".join(r[0] for r in results)
    for want in ("/ ", "/assets/index-abc123.js", "/manifest.webmanifest", "/api/summary", "evil.example", "POST",
                 "/../x", "/api/x", "listen"):
        assert want in names, (want, names)


@pytest.mark.parametrize("found", [
    [], ["0.0.0.0:{p}"], ["127.0.0.1:{p}", "0.0.0.0:{p}"], ["*:{p}"], ["[::]:{p}"], ["[::1]:{p}"],
    ["127.0.0.1:{p}", "[::1]:{p}"], ["127.0.0.2:{p}"],
])
def test_the_smoke_test_fails_unless_127_0_0_1_is_the_only_listener(proxy, viewer, found):
    port = proxy.server_address[1]
    results = sv.smoke(viewer, port, listeners=lambda p: [f.format(p=p) for f in found])
    bad = [r for r in results if not r[1]]
    assert [r[0] for r in bad] == [f"listen 127.0.0.1:{port} only"], results


def test_listeners_reads_ss(monkeypatch):
    out = "LISTEN 0 4096 127.0.0.1:8710 0.0.0.0:*\nLISTEN 0 4096 [::]:8710 [::]:*\n"
    calls = []

    def run(argv, **kw):
        calls.append(argv)
        return type("R", (), {"returncode": 0, "stdout": out, "stderr": ""})()
    monkeypatch.setattr(sv.subprocess, "run", run)
    assert sv.listeners(8710) == ["127.0.0.1:8710", "[::]:8710"]
    assert calls[0][:2] == ["ss", "-ltnH"]


def test_the_smoke_test_compares_assets_with_the_release_record(proxy, viewer):
    rel = Path(os.path.realpath(viewer.base / "current"))
    (rel / "assets").chmod(0o755)
    (rel / "assets" / "index-abc123.js").chmod(0o644)
    (rel / "assets" / "index-abc123.js").write_bytes(JS + b"//changed")
    port = proxy.server_address[1]
    bad = [r[0] for r in sv.smoke(viewer, port, listeners=lambda p: [f"127.0.0.1:{p}"]) if not r[1]]
    assert any("/assets/index-abc123.js" in b for b in bad), bad


def test_the_smoke_test_compares_the_summary_with_the_snapshot(tmp_path, proxy, viewer, ledger):
    ledger.upstream.close()
    shutil.rmtree(ledger.dir(LEDGER_RELEASE) / "sock")
    man = sd.manifest(ledger.data)
    ledger.upstream = Upstream(ledger, {**man, "cost_nano": man["cost_nano"] + 1})
    port = proxy.server_address[1]
    bad = [r[0] for r in sv.smoke(viewer, port, listeners=lambda p: [f"127.0.0.1:{p}"]) if not r[1]]
    assert bad and all("/api/summary" in b for b in bad), bad


# ---- S1: publishing and rollback -----------------------------------------------------------------------------------

def test_a_published_release_is_read_only_and_current_is_a_relative_link(viewer):
    link = viewer.base / "current"
    assert link.is_symlink() and not os.path.isabs(os.readlink(link))
    rel = Path(os.path.realpath(link))
    assert rel.parent == (viewer.base / "releases").resolve()
    for p in [rel, *rel.rglob("*")]:
        assert not p.stat().st_mode & 0o222, p
    rec = viewer.releases()[viewer.state()["live"]]
    assert rec["files"]["assets/index-abc123.js"] == hashlib.sha256(JS).hexdigest()
    assert rec["image"] and rec["dist_digest"]


def test_a_refused_dist_leaves_the_live_release_as_it_was(viewer):
    live, link = viewer.state()["live"], os.readlink(viewer.base / "current")
    with pytest.raises(sv.Refused, match="localStorage"):
        publish(viewer, "jbad-bbbbbbbbbbbb", **{"assets/index-abc123.js": JS + b"localStorage.x=1"})
    assert viewer.state()["live"] == live and os.readlink(viewer.base / "current") == link
    assert "jbad-bbbbbbbbbbbb" not in viewer.releases()
    assert not (viewer.base / "releases" / "jbad-bbbbbbbbbbbb").exists()


def test_a_release_is_live_only_after_its_smoke_test_passes(viewer, monkeypatch):
    live = viewer.state()["live"]
    monkeypatch.setattr(sv, "smoke", lambda *a, **k: [("/ -> 200", False, "broken")])
    with pytest.raises(sv.Refused, match="smoke"):
        publish(viewer, "jnew-cccccccccccc")
    assert viewer.state()["live"] == live
    assert os.path.realpath(viewer.base / "current").endswith(live)


def test_rollback_swaps_back_to_the_earlier_release(viewer):
    first = viewer.state()["live"]
    publish(viewer, "jnew-cccccccccccc", **{"assets/index-abc123.js": JS + b"//2"})
    assert viewer.state()["live"] == "jnew-cccccccccccc"
    assert sv.rollback(deps=deps(), viewer=viewer) == first
    assert viewer.state() == {"live": first, "history": [first]}
    assert os.path.realpath(viewer.base / "current").endswith(first)


def test_rollback_without_an_earlier_release_is_refused(viewer):
    with pytest.raises(sv.Refused, match="earlier"):
        sv.rollback(deps=deps(), viewer=viewer)


def test_rollback_to_a_release_that_changed_since_its_build_is_refused(viewer):
    first = viewer.state()["live"]
    publish(viewer, "jnew-cccccccccccc", **{"assets/index-abc123.js": JS + b"//2"})
    rel = viewer.base / "releases" / first
    rel.chmod(0o755)
    (rel / "extra.txt").write_text("x")
    with pytest.raises(sv.Refused, match="changed"):
        sv.rollback(deps=deps(), viewer=viewer)
    assert viewer.state()["live"] == "jnew-cccccccccccc"


def deps(yes=True):
    d = rj.Deps()
    d.assume_yes, d.echo = yes, Said()
    d.confirm = lambda text: False
    return d


def tree(path):
    return {str(p.relative_to(path)): (p.is_symlink() and os.readlink(p)) or (p.is_file() and p.read_bytes())
            for p in Path(path).rglob("*") if not p.is_socket()}


def test_a_viewer_rollback_does_not_touch_argus_ledger(viewer, ledger):
    publish(viewer, "jnew-cccccccccccc", **{"assets/index-abc123.js": JS + b"//2"})
    calls = []
    ledger.run = lambda *a, **k: (calls.append(a), (0, str(os.getpid()), ""))[1]
    outside = {p: tree(p) for p in (ledger.base / "releases", ledger.data)}
    state, log = ledger.state_path.read_bytes(), ledger.log_path.read_bytes() if ledger.log_path.exists() else b""
    sv.rollback(deps=deps(), viewer=viewer)
    assert ledger.state_path.read_bytes() == state
    assert (ledger.log_path.read_bytes() if ledger.log_path.exists() else b"") == log
    assert {p: tree(p) for p in outside} == outside
    assert all(a[0] == "inspect" for a in calls), calls


def test_a_ledger_rollback_does_not_touch_the_viewer(tmp_path, viewer, ledger, monkeypatch):
    other = "jledger-bbbbbbbbbbbb"
    ledger._save({"live": LEDGER_RELEASE, "history": [other, LEDGER_RELEASE]})
    ledger.note("built", release=other, job="jledger", repo="r", commit="b" * 40, runtime=sg.ENVIRONMENT,
                image=sg.V0_IMAGE)
    monkeypatch.setattr(sg, "runtime_image", lambda cfg, runtime=sg.ENVIRONMENT: sg.V0_IMAGE)
    monkeypatch.setattr(sg.Staging, "switch", lambda self, release, image, deps, why, commit_state: commit_state())
    ledger.run = lambda *a, **k: (0, "", "")
    before = tree(viewer.base)
    assert sg.rollback(cfg={}, deps=deps(), staging=ledger) == other
    assert tree(viewer.base) == before


def test_the_viewer_lives_in_its_own_directory_of_staging():
    v = sv.Viewer()
    assert v.base == sg.STAGING / "apps" / "viewer"
    assert v.ledger.base == sg.STAGING


# ---- the monitor ---------------------------------------------------------------------------------------------------

def test_the_monitor_runs_the_viewer_smoke_test_without_changing_the_release(viewer, ledger, monkeypatch):
    monkeypatch.setattr(sg.Staging, "smoke", lambda self, release, held=False: [("ledger", True, "")])
    seen = []

    def smoke(v, port, **kw):
        seen.append((v.base, port))
        return [("viewer", False, "down")]
    monkeypatch.setattr(sv, "smoke", smoke)
    state, link = viewer.state(), os.readlink(viewer.base / "current")
    rec = sd.monitor(ledger, sg.FIXTURE, viewer=viewer)
    assert seen == [(viewer.base, sv.PORT)]
    assert rec["viewer"]["release"] == state["live"] and rec["viewer"]["ok"] is False
    assert rec["ok"] is False
    assert viewer.state() == state and os.readlink(viewer.base / "current") == link


def test_the_monitor_without_a_viewer_release_checks_only_the_ledger(tmp_path, ledger, monkeypatch):
    monkeypatch.setattr(sg.Staging, "smoke", lambda self, release, held=False: [("ledger", True, "")])
    monkeypatch.setattr(sv, "smoke", lambda *a, **k: pytest.fail("no viewer release is live"))
    rec = sd.monitor(ledger, sg.FIXTURE, viewer=sv.Viewer(tmp_path / "none", ledger=ledger))
    assert rec["ok"] is True and rec["viewer"] is None


# ---- deploy (the build is faked; the real one is below) ------------------------------------------------------------

@pytest.fixture
def viewer_repo(tmp_path):
    r = tmp_path / "viewer_repo"
    shutil.copytree(DEMO, r)
    git(tmp_path, "init", "-q", str(r))
    git(r, "add", "-A")
    git(r, "commit", "-qm", "demo")
    return r, git(r, "rev-parse", "HEAD")


def viewer_job(jobs, job_id, repo, commit, environment=sv.ENVIRONMENT, **kw):
    applied_job(jobs, job_id, repo, commit, **kw)
    p = jobs / job_id / "job.json"
    data = json.loads(p.read_text())
    data["inputs"]["environment"] = environment
    p.write_text(json.dumps(data))
    return job_id


@pytest.fixture
def fake_build(monkeypatch):
    built = []

    def vite_build(src, out, image, *, run=None):
        built.append((Path(src), image))
        assert not os.access(src, os.W_OK)                 # the workspace is the read-only archive
        make_dist(Path(out))
        return {"exit_code": 0, "output": "built"}
    monkeypatch.setattr(sv, "vite_build", vite_build)
    monkeypatch.setattr(sv, "build_image", lambda cfg: "sha256:" + "2" * 64)
    return built


def test_deploy_builds_the_applied_commit_and_publishes_it(tmp_path, viewer, viewer_repo, fake_build, monkeypatch):
    r, commit = viewer_repo
    jobs = tmp_path / "jobs"
    job = viewer_job(jobs, "jview", r, commit)
    monkeypatch.setattr(sv, "smoke", lambda *a, **k: [("ok", True, "")])
    release = sv.deploy(job, cfg={}, deps=deps(), jobs_dir=jobs, viewer=viewer)
    assert release == f"jview-{commit[:12]}" and viewer.state()["live"] == release
    rec = viewer.releases()[release]
    assert (rec["commit"], rec["image"]) == (commit, "sha256:" + "2" * 64)
    assert len(fake_build) == 1
    assert any(e.get("what") == "staged" for e in json.loads((jobs / job / "job.json").read_text())["log"])


@pytest.mark.parametrize("change, why", [
    (lambda r: (r / "package.json").write_text(json.dumps({"dependencies": {"left-pad": "1.3.0"}})), "left-pad"),
    (lambda r: (r / "node_modules" / "react").mkdir(parents=True) or (r / "node_modules" / "react" / "x.js")
     .write_text("1"), "node_modules"),
    (lambda r: (r / "src" / "package.json").write_text("{}"), "package.json"),
])
def test_deploy_refuses_a_commit_that_would_not_build_from_the_environment(tmp_path, viewer, viewer_repo, fake_build,
                                                                           change, why):
    r, _ = viewer_repo
    change(r)
    git(r, "add", "-A", "-f")
    git(r, "commit", "-qm", "change")
    jobs = tmp_path / "jobs"
    live = viewer.state()["live"]
    with pytest.raises(sv.Refused, match=why):
        sv.deploy(viewer_job(jobs, "jview", r, git(r, "rev-parse", "HEAD")), cfg={}, deps=deps(), jobs_dir=jobs,
                  viewer=viewer)
    assert fake_build == [] and viewer.state()["live"] == live


@pytest.mark.parametrize("state, as_is, environment, why", [
    (rj.REVIEW_READY, True, sv.ENVIRONMENT, "only an APPLIED job"),
    (rj.APPLIED, False, sv.ENVIRONMENT, "differ from the reviewed patch"),
    (rj.APPLIED, True, "ledger_py312", "pwa_node22"),
])
def test_only_an_applied_viewer_job_is_deployed(tmp_path, viewer, viewer_repo, fake_build, state, as_is,
                                                 environment, why):
    r, commit = viewer_repo
    jobs = tmp_path / "jobs"
    job = viewer_job(jobs, "jview", r, commit, environment=environment, state=state, as_is=as_is)
    with pytest.raises(rj.Refused, match=why):
        sv.deploy(job, cfg={}, deps=deps(), jobs_dir=jobs, viewer=viewer)
    assert fake_build == []


def test_a_deploy_that_is_not_confirmed_changes_nothing(tmp_path, viewer, viewer_repo, fake_build):
    r, commit = viewer_repo
    jobs = tmp_path / "jobs"
    with pytest.raises(rj.Refused, match="not confirmed"):
        sv.deploy(viewer_job(jobs, "jview", r, commit), cfg={}, deps=deps(yes=False), jobs_dir=jobs, viewer=viewer)
    assert fake_build == [] and len(viewer.releases()) == 1


def test_a_failed_build_leaves_the_live_release_and_no_build_directory(tmp_path, viewer, viewer_repo, monkeypatch):
    r, commit = viewer_repo
    jobs = tmp_path / "jobs"
    monkeypatch.setattr(sv, "build_image", lambda cfg: "sha256:" + "2" * 64)
    monkeypatch.setattr(sv, "vite_build", lambda src, out, image, run=None: {"exit_code": 1, "output": "boom"})
    live = viewer.state()["live"]
    with pytest.raises(sv.Refused, match="boom"):
        sv.deploy(viewer_job(jobs, "jview", r, commit), cfg={}, deps=deps(), jobs_dir=jobs, viewer=viewer)
    assert viewer.state()["live"] == live
    assert [p.name for p in viewer.base.iterdir() if p.name.startswith(".build")] == []


# ---- with docker: the real build in pwa_node22 ---------------------------------------------------------------------

@pytest.fixture(scope="module")
def real_cfg():
    from approve_draft import sandbox_cfg
    cfg = load_config()
    cfg["sandbox"] = sandbox_cfg()
    try:
        sv.build_image(cfg)
    except rj.Refused as e:
        pytest.skip(f"SANDBOX NOT AVAILABLE: {e}")
    return cfg


def commit_config(r, config):
    (r / "vite.config.js").write_text(config)
    git(r, "add", "-A")
    git(r, "commit", "-qm", "config")
    return git(r, "rev-parse", "HEAD")


NET_PROBE = """import react from '@vitejs/plugin-react'
import fs from 'node:fs'

let net = 'offline'
try { await fetch('http://1.1.1.1/', { signal: AbortSignal.timeout(3000) }); net = 'online' } catch (e) {}
let wrote = 'no'
try { fs.writeFileSync('/workspace/x.txt', '1'); wrote = 'yes' } catch (e) {}
export default { plugins: [react(), { name: 'probe', generateBundle() {
  this.emitFile({ type: 'asset', fileName: 'probe.txt', source: `${net} ${wrote}` }) } }] }
"""


def test_the_real_build_runs_without_network_on_a_read_only_workspace(tmp_path, viewer_repo, real_cfg):
    r, _ = viewer_repo
    commit = commit_config(r, NET_PROBE)
    src, out = tmp_path / "src", tmp_path / "out"
    sg.unpack(r, commit, src)
    sd._writable(src)                                      # only the read-only mount keeps it as it is
    out.mkdir()
    res = sv.vite_build(src, out, sv.build_image(real_cfg))
    assert res["exit_code"] == 0, res
    assert (out / "probe.txt").read_text() == "offline no"
    assert (out / "index.html").is_file() and (out / "sw.js").read_bytes() == SW


def test_a_real_build_that_leaves_a_link_is_refused_and_the_live_release_stays(tmp_path, viewer, viewer_repo, real_cfg,
                                                                               monkeypatch):
    r, _ = viewer_repo
    commit = commit_config(r, """import react from '@vitejs/plugin-react'
import fs from 'node:fs'

export default { plugins: [react(), { name: 'link', writeBundle() { fs.symlinkSync('/etc/passwd', '/out/p.txt') } }] }
""")
    jobs = tmp_path / "jobs"
    live = viewer.state()["live"]
    with pytest.raises(sv.Refused, match="p.txt"):
        sv.deploy(viewer_job(jobs, "jview", r, commit), cfg=real_cfg, deps=deps(), jobs_dir=jobs, viewer=viewer)
    assert viewer.state()["live"] == live


def test_a_real_deploy_and_rollback(tmp_path, viewer, viewer_repo, real_cfg):
    r, commit = viewer_repo
    jobs = tmp_path / "jobs"
    first = viewer.state()["live"]
    release = sv.deploy(viewer_job(jobs, "jview", r, commit), cfg=real_cfg, deps=deps(), jobs_dir=jobs, viewer=viewer)
    assert viewer.state()["live"] == release
    index = (viewer.base / "current" / "index.html").read_text()
    assert "/assets/" in index and "/src/main.jsx" not in index
    assert sv.rollback(deps=deps(), viewer=viewer) == first


# ---- code review of PR 2 ----------------------------------------------------------------------------------------------

def test_current_is_put_back_on_the_recorded_release_before_a_command(viewer):
    first = viewer.state()["live"]
    publish(viewer, "jnew-cccccccccccc", **{"assets/index-abc123.js": JS + b"//2"})
    viewer._save({"live": first, "history": [first]})        # killed between the swap and the record
    with pytest.raises(sv.Refused, match="earlier"):
        sv.rollback(deps=deps(), viewer=viewer)
    assert viewer.published() == first


def test_a_release_whose_service_worker_is_no_longer_the_reviewed_one_is_not_published_again(viewer):
    first = viewer.state()["live"]
    publish(viewer, "jnew-cccccccccccc", **{"assets/index-abc123.js": JS + b"//2"})
    viewer.sw_sha256 = "f" * 64                               # SW_SHA256 moved on to another reviewed sw.js
    with pytest.raises(sv.Refused, match="sw.js"):
        sv.rollback(deps=deps(), viewer=viewer)
    assert viewer.state()["live"] == "jnew-cccccccccccc" and viewer.published() == "jnew-cccccccccccc"
    assert first in viewer.releases()


def test_a_known_release_built_on_another_image_is_not_published_again(tmp_path, viewer, viewer_repo, fake_build,
                                                                       monkeypatch):
    r, commit = viewer_repo
    jobs = tmp_path / "jobs"
    monkeypatch.setattr(sv, "smoke", lambda *a, **k: [("ok", True, "")])
    job = viewer_job(jobs, "jview", r, commit)
    sv.deploy(job, cfg={}, deps=deps(), jobs_dir=jobs, viewer=viewer)
    sv.rollback(deps=deps(), viewer=viewer)
    monkeypatch.setattr(sv, "build_image", lambda cfg: "sha256:" + "3" * 64)
    with pytest.raises(sv.Refused, match="image"):
        sv.deploy(job, cfg={}, deps=deps(), jobs_dir=jobs, viewer=viewer)
    assert viewer.state()["live"] != f"jview-{commit[:12]}"


def test_the_monitor_does_not_smoke_test_the_viewer_during_a_viewer_command(viewer, ledger, monkeypatch):
    monkeypatch.setattr(sg.Staging, "smoke", lambda self, release, held=False: [("ledger", True, "")])
    monkeypatch.setattr(sv, "smoke", lambda *a, **k: pytest.fail("the viewer lock is held"))
    with viewer.lock():
        rec = sd.monitor(ledger, sg.FIXTURE, viewer=viewer)
    assert rec["viewer"]["ok"] is None and "another viewer command" in rec["viewer"]["why"]
    assert rec["ok"] is True


def test_the_smoke_test_checks_relative_assets_and_skips_app_links(tmp_path, ledger):
    v = sv.Viewer(tmp_path / "rel", ledger=ledger, sw_sha256=SW_SHA)
    index = (b'<html><head><script type="module" src="./assets/index-abc123.js"></script></head>'
             b'<body><a href="/jobs/">jobs</a><a href="https://example.com/x.js">x</a></body></html>')
    publish(v, **{"index.html": index})
    srv = start(sv.make_server(v, port=0))
    try:
        results = sv.smoke(v, srv.server_address[1], listeners=None)
        assert [r for r in results if not r[1]] == [], results
        assert any(r[0] == "GET /assets/index-abc123.js -> 200 as recorded" for r in results), results
        rel = Path(os.path.realpath(v.base / "current"))
        (rel / "assets").chmod(0o755)
        (rel / "assets" / "index-abc123.js").chmod(0o644)
        (rel / "assets" / "index-abc123.js").write_bytes(b"changed")
        assert not all(r[1] for r in sv.smoke(v, srv.server_address[1], listeners=None))
    finally:
        srv.shutdown()
        srv.server_close()


def test_the_proxy_asks_docker_for_the_ledger_pid_once_and_again_after_a_restart(proxy, ledger, monkeypatch):
    pids = [os.getpid() + 1, os.getpid()]                     # a stale pid first, as after a container restart
    asked = []

    def container_pid(self, release):
        asked.append(release)
        return pids[min(len(asked) - 1, 1)]
    proxy.peer = (LEDGER_RELEASE, os.getpid() + 1)
    monkeypatch.setattr(sg.Staging, "container_pid", container_pid)
    assert request(proxy, "GET", "/api/summary")[0] == 502    # cached stale, docker still says stale
    assert request(proxy, "GET", "/api/summary")[0] == 200    # docker asked again: the real pid
    assert request(proxy, "GET", "/api/jobs")[0] == 200       # cached
    assert len(asked) == 2
