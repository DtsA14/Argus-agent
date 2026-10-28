"""SPEC_WEB_TOOLS (ReadDocs, stage 1): the downloader. URLs are checked before any connection, every address of a host
must be global, the connection goes to the checked address with TLS verified against the real host name, redirects are
checked again per hop, a response that does not fit is refused whole, and the child process runs with no environment.
No real network: the resolver and the connection are fakes, except a local TLS server for certificate verification."""
import json
import socket
import ssl
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from tools import web
from tools import web_fetch as wf

HOSTS = {"docs.python.org": r"/3(\.\d+)?/[A-Za-z0-9._~/-]*",
         "pypi.org": r"/pypi/[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)?/json"}
LIMITS = {"page_bytes": 2_000_000, "timeout_s": 15, "redirects": 3, "url_len": 300, "page_text": 400_000}
PUBLIC = "151.101.0.223"


# ---- 1. the URL, before any connection --------------------------------------------------------------------------------

@pytest.mark.parametrize("url", [
    "https://docs.python.org/3/library/json.html",
    "https://docs.python.org/3.12/library/sqlite3.html",
    "https://pypi.org/pypi/fastapi/json",
    "https://pypi.org/pypi/fastapi/0.143.0/json",
])
def test_allowed_urls(url):
    assert wf.check_url(url, HOSTS, LIMITS) is None


@pytest.mark.parametrize("url, why", [
    ("http://docs.python.org/3/library/json.html", "https"),
    ("https://docs.python.org:8443/3/library/json.html", "port"),
    ("https://docs.python.org:443/3/library/json.html", "port"),
    ("https://user:pw@docs.python.org/3/library/json.html", "userinfo"),
    ("https://user@docs.python.org/3/library/json.html", "userinfo"),
    ("https://docs.python.org/3/library/json.html?x=1", "query"),
    ("https://docs.python.org/3/library/json.html?", "query"),
    ("https://docs.python.org/3/library/json.html#top", "fragment"),
    ("https://docs.python.org/3/library/%6Ason.html", "path"),
    ("https://docs.python.org/3/../etc/passwd", "path"),
    ("https://docs.python.org/3/library/json html", "path"),
    ("https://docs.python.org/2/library/json.html", "path"),           # not the host's path pattern
    ("https://pypi.org/project/fastapi/", "path"),
    ("https://pypi.org/pypi/fastapi/json/simple", "path"),               # the pattern is matched whole, not as a prefix
    ("https://docs.python.org.evil.com/3/x.html", "host"),
    ("https://evil.docs.python.org/3/x.html", "host"),                  # no subdomains of an entry
    ("https://python.org/3/x.html", "host"),
    ("https://DOCS.PYTHON.ORG/3/x.html", "host"),                        # exact, as written in the allowlist
    ("https://151.101.0.223/3/x.html", "host"),
    ("https://[::1]/3/x.html", "host"),
    ("https://docs.python.org/3/" + "a" * 300, "long"),
    ("ftp://docs.python.org/3/x", "https"),
    ("https:///3/x.html", "host"),
    ("", "https"),
])
def test_refused_urls_name_why(url, why):
    reason = wf.check_url(url, HOSTS, LIMITS)
    assert reason and why in reason, (url, reason)


# ---- 2. the addresses -------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("ip", ["127.0.0.1", "10.0.0.5", "172.16.3.4", "192.168.1.1", "169.254.169.254", "100.64.0.1",
                                "0.0.0.0", "224.0.0.1", "255.255.255.255", "192.0.2.1", "198.18.0.1", "::1", "::",
                                "fe80::1", "fc00::1", "fd12::1", "ff02::1", "::ffff:127.0.0.1", "::ffff:10.0.0.1",
                                "::ffff:169.254.169.254", "2002:7f00:1::1", "64:ff9b::a00:1", "2001:db8::1",
                                "::127.0.0.1", "::ffff:8.8.8.8"])
def test_non_global_addresses_are_refused(ip):
    assert not wf.ip_ok(ip)


@pytest.mark.parametrize("ip", [PUBLIC, "8.8.8.8", "2a04:4e42::223"])
def test_global_addresses_are_accepted(ip):
    assert wf.ip_ok(ip)


# ---- 3. the fetch loop: one resolve per hop, the checked address used, redirects checked again ------------------------

class Net:
    """Fake DNS and HTTP: resolves[host] is a list of answers, one per call; pages[(host, path)] is (status, headers,
    body). Records which address each request went to."""

    def __init__(self, resolves, pages):
        self.resolves, self.pages, self.calls, self.gets = resolves, pages, [], []

    def resolve(self, host):
        self.calls.append(host)
        answers = self.resolves[host]
        return answers.pop(0) if len(answers) > 1 else answers[0]

    def get(self, host, ip, path, *, deadline, max_bytes):
        self.gets.append((host, ip, path))
        status, headers, body = self.pages[(host, path)]
        if isinstance(body, Exception):
            raise body
        if len(body) > max_bytes:
            raise wf.TooLarge(f"more than {max_bytes} bytes")
        return status, headers, body


def fetch(net, url="https://docs.python.org/3/library/json.html", limits=LIMITS):
    return wf.fetch(url, HOSTS, limits, resolve=net.resolve, get=net.get)


HTML = (b"<html><head><title>json</title><style>p{}</style><script>alert(1)</script></head><body><nav>menu</nav>"
        b"<h1>json</h1><p>Encode   and decode.</p><pre>  json.dumps(x)\n  json.loads(s)</pre></body></html>")
OK = (200, {"content-type": "text/html; charset=utf-8"}, HTML)


def test_a_page_is_fetched_from_the_checked_address_with_its_metadata():
    net = Net({"docs.python.org": [[PUBLIC]]}, {("docs.python.org", "/3/library/json.html"): OK})
    r = fetch(net)
    assert r["ok"] and net.gets == [("docs.python.org", PUBLIC, "/3/library/json.html")]
    assert r["final_url"] == "https://docs.python.org/3/library/json.html" and r["status"] == 200 and r["ip"] == PUBLIC
    assert r["bytes"] == len(HTML) and r["content_type"] == "text/html" and len(r["sha256"]) == 64
    assert r["chain"] == ["https://docs.python.org/3/library/json.html"]


def test_dns_rebinding_the_second_answer_is_never_used():
    net = Net({"docs.python.org": [[PUBLIC], ["127.0.0.1"]]}, {("docs.python.org", "/3/library/json.html"): OK})
    r = fetch(net)
    assert r["ok"] and net.calls == ["docs.python.org"] and net.gets[0][1] == PUBLIC


@pytest.mark.parametrize("answers", [["127.0.0.1"], [PUBLIC, "10.0.0.1"], ["169.254.169.254"], ["::ffff:127.0.0.1"], []])
def test_a_host_with_any_non_global_address_is_refused_before_connecting(answers):
    net = Net({"docs.python.org": [answers]}, {})
    r = fetch(net)
    assert not r["ok"] and net.gets == [] and "address" in r["reason"]


@pytest.mark.parametrize("location, why", [
    ("https://evil.example/3/x.html", "host"),
    ("http://docs.python.org/3/x.html", "https"),
    ("https://docs.python.org/3/x.html?a=1", "query"),
    ("https://pypi.org/simple/", "path"),
])
def test_a_redirect_is_checked_like_the_first_url(location, why):
    net = Net({"docs.python.org": [[PUBLIC]]},
              {("docs.python.org", "/3/library/json.html"): (301, {"location": location}, b"")})
    r = fetch(net)
    assert not r["ok"] and why in r["reason"] and len(net.gets) == 1


def test_a_redirect_to_an_allowed_host_resolves_and_checks_it_again():
    net = Net({"docs.python.org": [[PUBLIC]], "pypi.org": [["10.1.1.1"]]},
              {("docs.python.org", "/3/library/json.html"): (302, {"location": "https://pypi.org/pypi/x/json"}, b"")})
    r = fetch(net)
    assert not r["ok"] and "address" in r["reason"] and net.calls == ["docs.python.org", "pypi.org"]


def test_a_relative_redirect_and_at_most_three_hops():
    pages = {("docs.python.org", "/3/a"): (301, {"location": "/3/b"}, b""),
             ("docs.python.org", "/3/b"): (301, {"location": "/3/c"}, b""),
             ("docs.python.org", "/3/c"): (301, {"location": "/3/d"}, b""),
             ("docs.python.org", "/3/d"): OK}
    r = fetch(Net({"docs.python.org": [[PUBLIC]]}, pages), "https://docs.python.org/3/a")
    assert r["ok"] and r["chain"][-1] == "https://docs.python.org/3/d" and len(r["chain"]) == 4
    pages[("docs.python.org", "/3/d")] = (301, {"location": "/3/e"}, b"")
    pages[("docs.python.org", "/3/e")] = OK
    r = fetch(Net({"docs.python.org": [[PUBLIC]]}, pages), "https://docs.python.org/3/a")
    assert not r["ok"] and "redirects" in r["reason"]


@pytest.mark.parametrize("page, why", [
    ((404, {"content-type": "text/html"}, b"nope"), "HTTP 404"),
    ((200, {"content-type": "application/octet-stream"}, b"\x00"), "content type"),
    ((200, {"content-type": "image/png"}, b"x"), "content type"),
    ((200, {"content-type": "text/html"}, wf.TooLarge("more than 2000000 bytes")), "2000000"),
    ((200, {"content-type": "text/html"}, socket.timeout("timed out")), "timed out"),
    ((200, {"content-type": "text/html"}, ConnectionResetError("reset")), "reset"),
    ((200, {"content-type": "text/html"}, ssl.SSLCertVerificationError("bad cert")), "certificate"),
])
def test_a_response_that_does_not_fit_is_refused_whole(page, why):
    net = Net({"docs.python.org": [[PUBLIC]]}, {("docs.python.org", "/3/library/json.html"): page})
    r = fetch(net)
    assert not r["ok"] and why in r["reason"] and "text" not in r


def test_a_page_whose_text_is_too_long_is_refused_not_cut():
    big = b"<p>" + b"word " * 100_000 + b"</p>"
    net = Net({"docs.python.org": [[PUBLIC]]},
              {("docs.python.org", "/3/library/json.html"): (200, {"content-type": "text/html"}, big)})
    r = fetch(net, limits={**LIMITS, "page_text": 1000})
    assert not r["ok"] and "text" not in r and "1000" in r["reason"]


# ---- 4. the text -------------------------------------------------------------------------------------------------------

def test_html_becomes_text_without_scripts_styles_or_navigation():
    text = wf.to_text(HTML, "text/html")
    assert "alert" not in text and "p{}" not in text and "menu" not in text
    assert "# json" in text and "Encode and decode." in text
    assert "  json.dumps(x)\n  json.loads(s)" in text                         # pre keeps its layout


def test_json_is_pretty_printed_and_plain_text_kept():
    assert wf.to_text(b'{"info": {"version": "1.0"}}', "application/json") == \
        json.dumps({"info": {"version": "1.0"}}, indent=1, sort_keys=True)
    assert wf.to_text(b"plain\ntext", "text/plain") == "plain\ntext"


# ---- 5. the real connection: the checked address, TLS verified against the real host ---------------------------------

def test_the_connection_goes_to_the_checked_address_with_the_real_host_name(monkeypatch):
    seen = {}

    class Sock:
        def close(self):
            pass

    def create_connection(addr, timeout=None):
        seen["addr"] = addr
        return Sock()

    def wrap_socket(self, sock, server_hostname=None, **kw):
        seen["sni"], seen["check"], seen["verify"] = server_hostname, self.check_hostname, self.verify_mode
        raise ssl.SSLCertVerificationError("stop here")

    monkeypatch.setattr(wf.socket, "create_connection", create_connection)
    monkeypatch.setattr(ssl.SSLContext, "wrap_socket", wrap_socket)
    with pytest.raises(ssl.SSLCertVerificationError):
        wf.get_once("docs.python.org", PUBLIC, "/3/x.html", deadline=wf.now() + 5, max_bytes=100)
    assert seen == {"addr": (PUBLIC, 443), "sni": "docs.python.org", "check": True, "verify": ssl.CERT_REQUIRED}


@pytest.fixture(scope="module")
def tls_server(tmp_path_factory):
    """A local HTTPS server with a self-signed certificate for docs.python.org: not trusted, so the client must
    refuse it."""
    d = tmp_path_factory.mktemp("tls")
    key, cert = d / "k.pem", d / "c.pem"
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", str(key), "-out", str(cert),
                    "-days", "1", "-subj", "/CN=docs.python.org"], check=True, capture_output=True)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert, key)
    srv = socket.create_server(("127.0.0.1", 0))
    port = srv.getsockname()[1]

    def serve():
        while True:
            try:
                conn, _ = srv.accept()
            except OSError:
                return
            try:
                with ctx.wrap_socket(conn, server_side=True) as s:
                    s.recv(1024)
                    s.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: 2\r\n\r\nok")
            except (ssl.SSLError, OSError):
                pass
    threading.Thread(target=serve, daemon=True).start()
    yield port
    srv.close()


def test_an_untrusted_certificate_is_refused(tls_server, monkeypatch):
    real = socket.create_connection
    monkeypatch.setattr(wf.socket, "create_connection", lambda addr, timeout=None: real(("127.0.0.1", tls_server), timeout))
    with pytest.raises(ssl.SSLCertVerificationError):
        wf.get_once("docs.python.org", PUBLIC, "/3/x.html", deadline=wf.now() + 5, max_bytes=100)


# ---- 6. the child process: no environment, isolated mode, one JSON on stdout ------------------------------------------

def test_the_child_runs_isolated_with_an_empty_environment(monkeypatch):
    seen = {}

    def run(cmd, **kw):
        seen["cmd"], seen["env"] = cmd, kw.get("env")
        return subprocess.CompletedProcess(cmd, 0, json.dumps({"ok": False, "reason": "x", "chain": []}), "")

    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-secret")
    monkeypatch.setenv("HTTPS_PROXY", "http://10.0.0.1:3128")
    monkeypatch.setattr(web.subprocess, "run", run)
    web.spawn("https://docs.python.org/3/x.html", HOSTS, LIMITS)
    assert seen["env"] == {} and seen["cmd"][:3] == [sys.executable, "-I", "-S"]
    assert seen["cmd"][3] == str(Path(wf.__file__).resolve())


def test_the_real_child_answers_with_json_and_sees_no_environment():
    r = web.spawn("http://docs.python.org/3/x.html", HOSTS, LIMITS)          # refused before any network
    assert r == {"ok": False, "reason": r["reason"], "chain": []} and "https" in r["reason"]
    out = subprocess.run([sys.executable, "-I", "-S", str(Path(wf.__file__).resolve()), "--env"], env={},
                         capture_output=True, text=True, timeout=30)
    seen = json.loads(out.stdout)
    assert set(seen) <= {"LC_CTYPE"}, seen          # LC_CTYPE: set by Python itself at start (PEP 538), not inherited


def test_a_child_answer_of_the_wrong_shape_is_a_refusal(monkeypatch):
    for out in ("not json", json.dumps({"ok": True}), json.dumps([1]), ""):
        monkeypatch.setattr(web.subprocess, "run",
                            lambda cmd, out=out, **kw: subprocess.CompletedProcess(cmd, 0, out, ""))
        r = web.spawn("https://docs.python.org/3/x.html", HOSTS, LIMITS)
        assert r["ok"] is False and r["reason"]
