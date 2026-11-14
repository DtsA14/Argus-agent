"""SPEC_CHAT_APP C1 (sections 3 and 11): the chat service is read only. A real server on a free port; every refusal
happens on every route and method, and nothing the page shows comes from outside the allowlisted projection."""
import hashlib
import http.client
import json
import os
import re
import subprocess
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from router import chat as rc  # noqa: E402
from router import stage_viewer as sv  # noqa: E402
from test_control import JOB, make_job  # noqa: E402

HOST = "127.0.0.1:8712"
ROUTES = ["/", "/static/app.js", "/static/app.css", "/api/status", "/api/threads", f"/api/threads/{JOB}"]


class Service:
    def __init__(self, jobs):
        self.chat = rc.Chat(jobs)
        self.srv = rc.server(self.chat, port=0)
        self.port = self.srv.server_address[1]
        threading.Thread(target=lambda: self.srv.serve_forever(poll_interval=0.01), daemon=True).start()

    def stop(self):
        self.srv.shutdown()
        self.srv.server_close()

    def request(self, method, path, headers=None, host=HOST, body=b""):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        c.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
        h = {**({"Host": host} if host is not None else {}), **(headers or {})}
        if body:
            h["Content-Length"] = str(len(body))
        for k, v in h.items():
            c.putheader(k, v)
        c.endheaders()
        if body:
            c.send(body)
        r = c.getresponse()
        out = (r.status, {k.lower(): v for k, v in r.getheaders()}, r.read())
        c.close()
        return out

    def get_json(self, path, **kw):
        status, h, body = self.request("GET", path, **kw)
        return status, json.loads(body)


@pytest.fixture
def svc(tmp_path):
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    make_job(jobs)
    s = Service(jobs)
    s.jobs = jobs
    yield s
    s.stop()


def test_it_binds_127_0_0_1_on_8712_only(svc):
    assert (rc.BIND, rc.PORT) == ("127.0.0.1", 8712) and rc.HOSTS == ("127.0.0.1:8712",)
    assert svc.srv.server_address[0] == "127.0.0.1"


# ---- 11.1: the Host on every method and every route ------------------------------------------------------------------

@pytest.mark.parametrize("host", ["localhost:8712", "127.0.0.1:8711", "127.0.0.1:8710", "localhost:8710", "evil.example",
                                  "127.0.0.1", "127.0.0.1:8712.evil.example", "", None])
@pytest.mark.parametrize("path", ROUTES + ["/nothing"])
def test_a_foreign_host_is_refused_on_every_get_route(svc, host, path):
    status, _, body = svc.request("GET", path, host=host)
    assert status == 421 and b"wrong host" in body
    assert b"argus" not in body.lower() or b"refused" in body


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
def test_every_other_method_is_refused_and_never_acts(svc, method):
    assert svc.request(method, "/api/threads", body=b"x=1" if method == "POST" else b"")[0] == 405
    assert svc.request(method, "/api/threads", host="evil.example")[0] == 421


def test_a_post_with_a_body_does_not_poison_the_next_request(svc):
    import socket
    smuggled = b"GET /api/status HTTP/1.1\r\nHost: 127.0.0.1:8712\r\n\r\n"
    raw = (b"POST /api/threads HTTP/1.1\r\nHost: 127.0.0.1:8712\r\nContent-Length: %d\r\n\r\n" % len(smuggled)) + smuggled
    with socket.create_connection(("127.0.0.1", svc.port), timeout=5) as c:
        c.sendall(raw)
        data = b""
        while True:
            chunk = c.recv(4096)
            if not chunk:
                break
            data += chunk
    assert data.count(b"HTTP/1.") == 1 and data.split(b" ", 2)[1] == b"405"
    assert b"threads" not in data and b'"jobs"' not in data                      # the request inside the body was never answered


# ---- 11.1: Sec-Fetch-Site on /api/* (same-site is the viewer on localhost:8710) -------------------------------------

@pytest.mark.parametrize("site, ok", [(None, True), ("same-origin", True), ("none", True), ("same-site", False),
                                      ("cross-site", False), ("weird", False)])
def test_sec_fetch_site_on_the_api(svc, site, ok):
    headers = {"Sec-Fetch-Site": site} if site else {}
    for path in ("/api/status", "/api/threads", f"/api/threads/{JOB}"):
        assert (svc.request("GET", path, headers)[0] == 200) is ok


# ---- 11.2: no cookie in, none out -----------------------------------------------------------------------------------

@pytest.mark.parametrize("path", ROUTES + ["/nothing"])
def test_no_set_cookie_ever_and_a_huge_cookie_is_ignored(svc, path):
    status, h, _ = svc.request("GET", path, {"Cookie": "a=" + "b" * 6000})
    assert "set-cookie" not in h and status in (200, 404)


# ---- headers on every answer -----------------------------------------------------------------------------------------

@pytest.mark.parametrize("req", [("GET", "/", HOST), ("GET", "/api/status", HOST), ("GET", "/nothing", HOST),
                                 ("POST", "/api/status", HOST), ("GET", "/", "evil.example")])
def test_every_answer_carries_the_security_headers(svc, req):
    method, path, host = req
    _, h, _ = svc.request(method, path, host=host)
    assert h["content-security-policy"] == rc.csp()
    assert h["x-frame-options"] == "DENY" and h["x-content-type-options"] == "nosniff"
    assert h["cross-origin-resource-policy"] == "same-origin" and h["cross-origin-opener-policy"] == "same-origin"
    assert h["cache-control"] == "no-store" and h["referrer-policy"] == "same-origin"
    assert not any(k.startswith("access-control-") for k in h)


def test_the_csp_is_as_strict_as_the_spec_says():
    c = rc.csp()
    for part in ("default-src 'none'", "script-src http://127.0.0.1:8712/static/app.js", "form-action 'none'",
                 "frame-ancestors 'none'", "base-uri 'none'", "worker-src 'none'", "require-trusted-types-for 'script'",
                 "trusted-types 'none'"):
        assert part in c
    assert "unsafe-inline" not in c and "unsafe-eval" not in c and "*" not in c


# ---- routes ----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("path", ["/api/", "/api/threads/", "/api/threads/x", f"/api/threads/{JOB}/", f"/api/threads/{JOB}?x=1",
                                  "/api/status?x=1", "/api/STATUS", "/index.html", "/static/", "/static/app.js?v=1",
                                  "/static/../router/chat.py", "/static/%61pp.js", f"/api/threads/{JOB[:-1]}%64",
                                  "/api/threads/..%2Fx", "/api/threads/" + "j" * 300, "/chat/x", "/jobs/" + JOB])
def test_anything_but_the_fixed_routes_is_404(svc, path):
    assert svc.request("GET", path)[0] == 404


def test_the_api_answers_json_with_nosniff(svc):
    for path in ("/api/status", "/api/threads", f"/api/threads/{JOB}", "/api/nothing"):
        _, h, body = svc.request("GET", path)
        assert h["content-type"].startswith("application/json") and h["x-content-type-options"] == "nosniff"
        json.loads(body)


# ---- what is shown ---------------------------------------------------------------------------------------------------

def test_the_list_and_the_detail_show_the_projection(svc):
    status, d = svc.get_json("/api/threads")
    assert status == 200 and d["skipped"] == 0
    (t,) = d["threads"]
    assert t["id"] == JOB and t["state"] == "AWAITING_APPROVAL" and t["kind"] == "code" and t["max_usd"] == 1.0
    status, d = svc.get_json(f"/api/threads/{JOB}")
    assert status == 200 and d["job"]["id"] == JOB and "d1" in d["job"]["stages"] and d["spent_usd"] == 0
    assert "inputs" not in json.dumps(d) and "/nowhere" not in json.dumps(d)       # the issue text and the repo path stay out


def test_cost_comes_from_the_ledger(svc):
    run = svc.jobs / JOB / "runs" / f"{JOB}-d1"
    base = {"call_id": "c1", "model": "anthropic:claude-haiku-4-5", "node": "draft", "role": "draft", "ts": 1.0}
    evs = [{"event": "llm_call_started", **base, "worst_usd_nano": 20_000_000, "worst_tokens": 100},
           {"event": "llm_call", **base, "status": "ok", "usd_nano": 12_000_000, "tokens": 10, "input_tokens": 5,
            "output_tokens": 5, "cache_read": None, "est_input": 5}]
    (run / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in evs), encoding="utf-8")
    assert svc.get_json(f"/api/threads/{JOB}")[1]["spent_usd"] == pytest.approx(0.012)


def test_only_ui_shaped_names_are_listed_and_a_symlinked_job_is_never_read(svc, tmp_path):
    (svc.jobs / "notes").mkdir()
    (svc.jobs / "j1").mkdir()
    secret = tmp_path / "secret"
    (secret / "runs").mkdir(parents=True)
    (secret / "job.json").write_text(json.dumps({"job": "j20261109_130000_beef", "kind": "code", "state": "DONE",
                                                 "max_usd": 1.0, "created_at": "2026-11-09T13:00:00Z", "stages": {}}))
    os.symlink(secret, svc.jobs / "j20261109_130000_beef")
    ids = [t["id"] for t in svc.get_json("/api/threads")[1]["threads"]]
    assert ids == [JOB] and svc.get_json("/api/threads")[1]["skipped"] == 1   # only the symlink is tried (and refused); 'notes' and 'j1' never are
    assert svc.get_json("/api/threads/j20261109_130000_beef")[0] == 404


def test_a_job_with_a_key_in_a_field_is_counted_not_shown(svc):
    other = "j20261109_140000_cafe"
    make_job(svc.jobs, other)
    p = svc.jobs / other / "job.json"
    d = json.loads(p.read_text())
    d["state"] = "sk-ant-api03-AAAAAAAAAAAAAAAA"          # a value that is not an allowed state: the job is excluded
    p.write_text(json.dumps(d))
    out = svc.get_json("/api/threads")[1]
    assert [t["id"] for t in out["threads"]] == [JOB] and out["skipped"] == 1
    assert "sk-ant" not in json.dumps(out)


def test_a_title_with_invisible_characters_is_cleaned(svc):
    p = svc.jobs / JOB / "job.json"
    d = json.loads(p.read_text())
    d["inputs"]["issue"] = "Fix the ‮title‬​ of the page\nsecond line"
    p.write_text(json.dumps(d))
    t = svc.get_json("/api/threads")[1]["threads"][0]
    assert t["title"] == "Fix the title of the page"


def test_the_list_is_capped(tmp_path):
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    for i in range(rc.LIST_MAX + 5):
        make_job(jobs, f"j20261109_{i:06d}_abcd")
    s = Service(jobs)
    try:
        out = s.get_json("/api/threads")[1]
        assert len(out["threads"]) == rc.LIST_MAX
        assert out["threads"][0]["id"] > out["threads"][-1]["id"]            # newest first
    finally:
        s.stop()


def test_a_missing_jobs_directory_is_an_empty_list(tmp_path):
    s = Service(tmp_path / "nowhere")
    try:
        assert s.get_json("/api/threads")[1] == {"threads": [], "skipped": 0}
    finally:
        s.stop()


# ---- Status mode calls no model and starts no process -----------------------------------------------------------------

def test_no_route_starts_a_process(svc, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("the chat started a process")
    monkeypatch.setattr(subprocess, "run", boom)
    monkeypatch.setattr(subprocess, "Popen", boom)
    for path in ROUTES:
        assert svc.request("GET", path)[0] == 200
    for method in ("POST", "PUT", "DELETE"):
        svc.request(method, "/api/threads")


def test_the_module_imports_no_model_and_no_subprocess():
    src = (Path(rc.__file__)).read_text()
    for banned in ("subprocess", "harness.llm", "LLMCaller", "build_chat_model", ".invoke(", "os.system", "Popen"):
        assert banned not in src


# ---- the shipped files are pinned and carry no HTML sink --------------------------------------------------------------

def test_the_shipped_files_are_the_pinned_ones():
    for name in rc.STATIC_TYPES:
        assert hashlib.sha256((rc.STATIC_DIR / name).read_bytes()).hexdigest() == rc.STATIC_SHA256[name]


def test_a_changed_static_file_stops_the_service(tmp_path, monkeypatch):
    for name in rc.STATIC_TYPES:
        (tmp_path / name).write_bytes((rc.STATIC_DIR / name).read_bytes())
    (tmp_path / "app.js").write_bytes(b"alert(1)")
    monkeypatch.setattr(rc, "STATIC_DIR", tmp_path)
    with pytest.raises(RuntimeError):
        rc.load_static()


SINKS = ["innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function", "createContextualFragment",
         "DOMParser", "srcdoc", "setHTMLUnsafe", "parseHTMLUnsafe", "Worker(", "serviceWorker", "window.open", "import(",
         "localStorage", "sessionStorage", "indexedDB", "document.cookie", "XMLHttpRequest", "WebSocket", "EventSource",
         "postMessage", "location =", "location.href", ".href =", "javascript:"]


@pytest.mark.parametrize("sink", SINKS)
def test_the_page_script_has_no_html_sink_or_storage(sink):
    assert sink not in (rc.STATIC_DIR / "app.js").read_text()


def test_the_script_does_not_listen_for_messages_or_pass_a_string_to_a_timer():
    js = (rc.STATIC_DIR / "app.js").read_text()
    assert not re.search(r'addEventListener\(\s*["\']message', js) and "onmessage" not in js
    for m in re.finditer(r"set(?:Timeout|Interval)\(\s*([^,)]*)", js):
        assert not m.group(1).strip().startswith(('"', "'", "`"))


def test_the_page_has_one_external_script_and_no_inline_code():
    html = (rc.STATIC_DIR / "index.html").read_text()
    assert re.findall(r"<script\b[^>]*>", html) == ['<script src="/static/app.js">']
    assert not re.search(r"<script[^>]*>[^<]+</script>", html)
    assert not re.search(r"\son[a-z]+\s*=", html) and "<style" not in html and "javascript:" not in html


def test_the_viewer_proxy_still_forwards_nothing_to_the_chat():
    assert "chat" not in sv.API.pattern and sv.API.match("/api/threads") is None


# ---- one Host, one Sec-Fetch-Site (found by probing: the first of two used to stand in for both) -------------------------

def raw_get(svc, headers):
    import socket
    req = b"GET /api/status HTTP/1.1\r\n" + b"".join(f"{k}: {v}\r\n".encode() for k, v in headers) + b"\r\n"
    with socket.create_connection(("127.0.0.1", svc.port), timeout=5) as c:
        c.sendall(req)
        data = b""
        while True:
            chunk = c.recv(4096)
            if not chunk:
                break
            data += chunk
    return int(data.split(b" ", 2)[1])


@pytest.mark.parametrize("hosts", [[HOST, "evil.example"], ["evil.example", HOST], [HOST, HOST], []])
def test_exactly_one_host_header_is_required(svc, hosts):
    assert raw_get(svc, [("Host", h) for h in hosts]) == 421


def test_one_good_host_header_is_accepted_in_the_raw_helper(svc):
    assert raw_get(svc, [("Host", HOST)]) == 200


@pytest.mark.parametrize("sites", [["same-origin", "cross-site"], ["cross-site", "same-origin"], ["same-origin", "same-origin"]])
def test_two_sec_fetch_site_headers_are_refused(svc, sites):
    assert raw_get(svc, [("Host", HOST)] + [("Sec-Fetch-Site", x) for x in sites]) == 403
