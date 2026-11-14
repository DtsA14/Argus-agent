"""SPEC_CHAT_APP C2a (sections 1.3, 3, 11.3, 11.5, 11.6, 11.8, 11.10, 11.14): the issue writer's actions in two steps, prepare then confirm.
A real server on a free port; the CLI is a recorder (no process, no model, no money)."""
import http.client
import json
import os
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from router import chat as rc  # noqa: E402
from router import chat_actions as ca  # noqa: E402
from router import issue as ri  # noqa: E402

HOST, ORIGIN = "127.0.0.1:8712", "http://127.0.0.1:8712"
NOW = 1_794_700_000.0                      # 2026-11-15T22:26:40Z
KEY, WKEY = "/keys/code.key", "/keys/writer.key"
CFG = {"issue_writer": {"role": "issue_writer", "max_usd": 0.5, "message_max": 4000, "reply_max": 2000, "code_max_usd": 1.0,
                        "turn": {"cap_usd": 0.1},
                        "repos": {"argus-viewer": {"path": "~/argus-viewer", "environment": "pwa_node22"}}},
       "chat": {"daily_cap_usd": 2.0}}


class Clock:
    def __init__(self):
        self.t = NOW

    def __call__(self):
        return self.t


class FakeSpawner:
    def __init__(self, state):
        self.state, self.calls, self.busy_ids = Path(state), [], set()

    def spawn(self, job_id, argv, message=None, action="", text=None):
        self.calls.append({"job": job_id, "argv": argv, "message": message, "action": action, "text": text})

    def busy(self, job_id):
        return job_id in self.busy_ids

    def outcome(self, job_id):
        return None

    def message_file(self, text):
        p = self.state / "messages" / f"m{len(self.calls)}.txt"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        return p


def iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def make_issue(jobs, job_id, state=ri.AWAITING_HUMAN, turn=2, issue="Title line\n\nBody of the issue.\n", handoff=None, created=NOW - 100,
               via="ui", max_usd=0.5, conversation=None):
    d = jobs / job_id
    d.mkdir(parents=True)
    conv = conversation if conversation is not None else [
        {"from": "human", "text": "please add a thing"},
        {"from": "writer", "text": "ok, here is the issue", "questions": [], "clashes": []}][:turn]
    data = {"job": job_id, "kind": "issue", "state": state, "max_usd": max_usd, "created_at": iso(created),
            "inputs": {"repo": "/secret/path/argus-viewer", "repo_name": "argus-viewer", "commit": "9e78ed13b03f0000",
                       "environment": "pwa_node22"},
            "conversation": conv, "issue_sha256": "x", "log": [{"at": iso(created), "what": "created", "via": via}]}
    if handoff:
        data["handoff"] = handoff
    (d / "job.json").write_text(json.dumps(data))
    if issue is not None:
        (d / ri.ISSUE).write_text(issue)
    return d


class Service:
    def __init__(self, tmp, cfg=CFG, environ=None, clock=None, run=None):
        self.jobs = tmp / "jobs"
        self.jobs.mkdir(exist_ok=True)
        self.clock = clock or Clock()
        self.spawner = FakeSpawner(tmp / "state")
        self.runs = []

        def fake_run(action, job_id, reason):
            self.runs.append((action, job_id, reason))
            return (run or (lambda *a: (0, "ok")))(action, job_id, reason)
        self.actions = ca.Actions(self.jobs, cfg, state=tmp / "state", clock=self.clock,
                                  environ={ca.WRITER_KEY_ENV: WKEY, ca.KEY_ENV: KEY} if environ is None else environ,
                                  spawner=self.spawner, run=fake_run)
        self.chat = rc.Chat(self.jobs, clock=self.clock, actions=self.actions)
        self.srv = rc.server(self.chat, port=0)
        self.port = self.srv.server_address[1]
        threading.Thread(target=lambda: self.srv.serve_forever(poll_interval=0.01), daemon=True).start()

    def stop(self):
        self.srv.shutdown()
        self.srv.server_close()

    def request(self, method, path, body=None, headers=None, host=HOST, raw=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else b"")
        h = {"Host": host, **({"Origin": ORIGIN, "Content-Type": "application/json"} if method == "POST" else {}), **(headers or {})}
        if method == "POST" and "Content-Length" not in h:
            h["Content-Length"] = str(len(data))
        c.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
        for k, v in h.items():
            if v is not None:
                c.putheader(k, v)
        c.endheaders()
        if data:
            c.send(data)
        r = c.getresponse()
        out = (r.status, r.read())
        c.close()
        return out[0], (json.loads(out[1]) if out[1] else None)

    def prepare(self, **body):
        return self.request("POST", "/api/prepare", body)

    def confirm(self, token, wait=True):
        if wait:
            self.clock.t += ca.MIN_DELAY + 0.1
        return self.request("POST", "/api/confirm", {"token": token})

    def audit(self):
        p = self.actions.audit_path
        return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []


@pytest.fixture
def svc(tmp_path):
    s = Service(tmp_path)
    yield s
    s.stop()


JOB = "j20261115_220000_abcd"
NEW = {"action": "issue_new", "repo": "argus-viewer", "message": "tambahkan tombol di halaman daftar"}


# ---- prepare: a card, no process, no money -----------------------------------------------------------------------------

def test_prepare_a_new_issue_shows_what_will_run_and_runs_nothing(svc):
    status, out = svc.prepare(**NEW)
    assert status == 200 and out["card"]["repo"] == "argus-viewer" and out["card"]["environment"] == "pwa_node22"
    assert out["card"]["message"] == NEW["message"] and out["card"]["turn_cap_usd"] == 0.1 and out["card"]["job_cap_usd"] == 0.5
    assert out["exposure_usd"] == 0.5 and len(out["token"]) >= 40 and out["min_delay_s"] == ca.MIN_DELAY
    assert svc.spawner.calls == [] and svc.runs == []


def test_a_token_is_random_and_different_each_time(svc):
    assert svc.prepare(**NEW)[1]["token"] != svc.prepare(**NEW)[1]["token"]


@pytest.mark.parametrize("body, status", [
    ({"action": "nothing"}, 404), ({"action": "issue_new", "repo": "elsewhere", "message": "x"}, 400),
    ({"action": "issue_new", "repo": "argus-viewer", "message": ""}, 400),
    ({"action": "issue_new", "repo": "argus-viewer", "message": "x" * 4001}, 400),
    ({"action": "issue_new", "repo": "argus-viewer", "message": "a‮b"}, 400),
    ({"action": "issue_new", "repo": "argus-viewer", "message": "x", "path": "/etc"}, 400),
    ({"action": "issue_new", "repo": "argus-viewer", "message": 5}, 400), ({"action": 3}, 404),
])
def test_prepare_refuses_a_bad_form_without_a_token(svc, body, status):
    s, out = svc.prepare(**body)
    assert s == status and "token" not in json.dumps(out)


def test_no_key_for_the_service_means_no_card(tmp_path):
    s = Service(tmp_path, environ={})
    try:
        assert s.prepare(**NEW)[0] == 409
    finally:
        s.stop()


def test_the_start_card_shows_the_issue_text_itself_scrubbed(svc):
    make_issue(svc.jobs, JOB, issue="Fix ‮the​ page\n\nsecret sk-ant-api03-AAAAAAAAAAAAAAAAAAAA here\n")
    s, out = svc.prepare(action="issue_start", job=JOB)
    c = out["card"]
    assert s == 200 and c["issue_title"] == "Fix the page" and "‮" not in c["issue_text"] and "​" not in c["issue_text"]
    assert "sk-ant" not in json.dumps(out) and "withheld" in c["issue_text"]
    assert c["repo"] == "argus-viewer" and c["commit"] == "9e78ed13b03f" and c["environment"] == "pwa_node22"
    assert c["job_cap_usd"] == 1.0 and out["exposure_usd"] == 1.0 and "/secret/path" not in json.dumps(out)


@pytest.mark.parametrize("action, state, status", [
    ("issue_start", ri.WRITING, 409), ("issue_start", ri.HANDED_OFF, 409), ("issue_reply", ri.WRITING, 409),
    ("issue_reply", ri.HANDED_OFF, 409), ("issue_abandon", ri.HANDED_OFF, 409), ("issue_abandon", ri.WRITING, 409)])
def test_the_card_is_refused_in_a_state_that_cannot_take_the_action(svc, action, state, status):
    make_issue(svc.jobs, JOB, state=state)
    assert svc.prepare(action=action, job=JOB, message="more", reason="")[0] == status


def test_a_busy_writer_gets_no_card(svc):
    make_issue(svc.jobs, JOB)
    svc.spawner.busy_ids.add(JOB)
    assert svc.prepare(action="issue_reply", job=JOB, message="x")[0] == 409


def test_a_job_id_that_is_not_ui_shaped_or_not_an_issue_gets_404(svc):
    make_issue(svc.jobs, JOB)
    for j in ("..", "j1", "../x", "J20261115_220000_ABCD"):
        assert svc.prepare(action="issue_start", job=j)[0] == 404
    d = svc.jobs / "j20261115_220001_abcd"
    d.mkdir()
    (d / "job.json").write_text(json.dumps({"job": d.name, "kind": "code", "state": "DONE", "inputs": {}}))
    assert svc.prepare(action="issue_start", job=d.name)[0] == 404


# ---- confirm: the token only, the card rebuilt, the CLI the gate ---------------------------------------------------------

def test_confirm_a_new_issue_starts_the_cli_with_the_key_file_and_the_message_in_a_file(svc):
    token = svc.prepare(**NEW)[1]["token"]
    status, out = svc.confirm(token)
    assert status == 200 and out["started"] is True and ca.UI_ID.fullmatch(out["job"])
    (call,) = svc.spawner.calls
    argv = call["argv"]
    assert argv[argv.index("issue") + 1] == "new" and "--via" in argv and argv[argv.index("--via") + 1] == "ui"
    assert argv[argv.index("--key-file") + 1] == WKEY and "--repo" in argv and "argus-viewer" in argv
    assert NEW["message"] not in " ".join(argv) and "--message-file" in argv and call["text"] == NEW["message"]


def test_a_token_works_once(svc):
    token = svc.prepare(**NEW)[1]["token"]
    assert svc.confirm(token)[0] == 200
    assert svc.confirm(token)[0] == 403 and len(svc.spawner.calls) == 1


def test_a_confirm_too_soon_is_refused_and_the_token_is_kept(svc):
    token = svc.prepare(**NEW)[1]["token"]
    assert svc.confirm(token, wait=False)[0] == 429 and svc.spawner.calls == []
    assert svc.confirm(token)[0] == 200


def test_an_expired_token_is_refused(svc):
    token = svc.prepare(**NEW)[1]["token"]
    svc.clock.t += ca.TOKEN_TTL + 1
    assert svc.confirm(token, wait=False)[0] == 403 and svc.spawner.calls == []


@pytest.mark.parametrize("body", [{"token": "nope"}, {"token": ""}, {"token": 5}, {}, {"token": "x", "action": "issue_start"},
                                  {"token": "x", "job": JOB}])
def test_confirm_carries_the_token_and_nothing_else(svc, body):
    status, _ = svc.request("POST", "/api/confirm", body)
    assert status in (400, 403) and svc.spawner.calls == []


def test_the_card_that_changed_since_it_was_shown_is_refused(svc):
    d = make_issue(svc.jobs, JOB)
    token = svc.prepare(action="issue_start", job=JOB)[1]["token"]
    (d / ri.ISSUE).write_text("A different issue, written after the card was shown\n")      # the writer answered meanwhile
    status, out = svc.confirm(token)
    assert status == 409 and "changed" in out["refused"] and svc.spawner.calls == []
    assert svc.confirm(token)[0] == 403                                                      # and the token is spent


def test_a_reply_card_is_bound_to_the_turn(svc):
    d = make_issue(svc.jobs, JOB)
    token = svc.prepare(action="issue_reply", job=JOB, message="and also this")[1]["token"]
    data = json.loads((d / "job.json").read_text())
    data["conversation"].append({"from": "writer", "text": "one more answer"})
    (d / "job.json").write_text(json.dumps(data))
    assert svc.confirm(token)[0] == 409 and svc.spawner.calls == []


def test_confirm_uses_the_stored_action_not_anything_the_client_sends(svc):
    make_issue(svc.jobs, JOB)
    token = svc.prepare(action="issue_reply", job=JOB, message="this one")[1]["token"]
    svc.clock.t += 2
    assert svc.request("POST", "/api/confirm", {"token": token, "message": "another"})[0] == 400
    assert svc.confirm(token)[0] == 200
    assert svc.spawner.calls[0]["text"] == "this one" and svc.spawner.calls[0]["job"] == JOB


def test_start_runs_the_cli_with_the_sha_the_card_showed(svc):
    make_issue(svc.jobs, JOB)
    out = svc.prepare(action="issue_start", job=JOB)[1]
    assert svc.confirm(out["token"])[0] == 200
    argv = svc.spawner.calls[0]["argv"]
    assert argv[argv.index("start") + 1:argv.index("start") + 3] == ["--sha", out["card"]["sha12"]] and argv[-2:] == ["--", JOB]
    assert argv[argv.index("--key-file") + 1] == KEY


def test_abandon_is_run_at_once_and_a_refusal_of_the_cli_is_shown(tmp_path):
    s = Service(tmp_path, run=lambda a, j, r: (1, "refused: not today"))
    try:
        make_issue(s.jobs, JOB)
        out = s.prepare(action="issue_abandon", job=JOB, reason="no longer needed")[1]
        status, body = s.confirm(out["token"])
        assert status == 409 and body["refused"] == "not today" and s.runs == [("abandon", JOB, "no longer needed")]
    finally:
        s.stop()


def test_prepare_for_a_reply_never_runs_the_cli(svc):
    make_issue(svc.jobs, JOB)
    assert svc.prepare(action="issue_reply", job=JOB, message="x")[0] == 200
    assert svc.prepare(action="issue_abandon", job=JOB, reason="y")[0] == 200
    assert svc.spawner.calls == [] and svc.runs == []


# ---- 11.8: the daily exposure -----------------------------------------------------------------------------------------------

def ids(n):
    return [f"j20261115_2{i:05d}_abcd"[:20] for i in range(n)]


def test_the_cap_counts_the_full_max_usd_of_jobs_started_from_the_ui_in_24_hours(svc):
    for i, j in enumerate(["j20261115_100000_aaaa", "j20261115_110000_aaaa", "j20261115_120000_aaaa"]):
        make_issue(svc.jobs, j, created=NOW - 3600 * (i + 1))
    make_issue(svc.jobs, "j20261113_100000_aaaa", created=NOW - 3600 * 60)                 # two days ago: not counted
    make_issue(svc.jobs, "j20261115_130000_aaaa", created=NOW - 3600, via="cli")             # not from the UI
    assert svc.actions.exposure() == pytest.approx(1.5)


def test_a_start_made_from_the_ui_counts_the_code_cap(svc):
    make_issue(svc.jobs, JOB, state=ri.HANDED_OFF, created=NOW - 3600, via="ui",
               handoff={"job": "j20261115_230000_beef", "at": iso(NOW - 600), "via": "ui"})
    assert svc.actions.exposure() == pytest.approx(0.5 + 1.0)


def test_a_new_issue_is_refused_when_the_cap_would_be_passed(svc):
    for j in ("j20261115_100000_aaaa", "j20261115_110000_aaaa", "j20261115_120000_aaaa", "j20261115_130000_aaaa"):
        make_issue(svc.jobs, j, created=NOW - 3600)
    token = svc.prepare(**NEW)[1]["token"]
    status, out = svc.confirm(token)
    assert status == 403 and "daily cap" in out["refused"] and svc.spawner.calls == []


def test_two_confirms_back_to_back_cannot_beat_the_cap(tmp_path):
    cfg = json.loads(json.dumps(CFG))
    cfg["chat"]["daily_cap_usd"] = 0.6
    s = Service(tmp_path, cfg=cfg)
    try:
        t1, t2 = s.prepare(**NEW)[1]["token"], s.prepare(**NEW)[1]["token"]
        assert s.confirm(t1)[0] == 200          # the job directory does not exist yet: the pending record counts
        assert s.confirm(t2)[0] == 403 and len(s.spawner.calls) == 1
    finally:
        s.stop()


def test_a_reply_and_an_abandon_are_not_blocked_by_the_cap(svc):
    for j in ("j20261115_100000_aaaa", "j20261115_110000_aaaa", "j20261115_120000_aaaa", "j20261115_130000_aaaa"):
        make_issue(svc.jobs, j, created=NOW - 3600)
    make_issue(svc.jobs, JOB)
    t = svc.prepare(action="issue_reply", job=JOB, message="more")[1]["token"]
    assert svc.confirm(t)[0] == 200


def test_an_unreadable_job_in_the_window_means_the_cap_cannot_be_computed(svc):
    d = svc.jobs / "j20261115_150000_aaaa"
    d.mkdir()
    (d / "job.json").write_text("{not json")
    token = svc.prepare(**NEW)[1]["token"]
    status, _ = svc.confirm(token)
    assert status == 503 and svc.spawner.calls == []


def test_a_job_with_a_garbled_time_means_the_cap_cannot_be_computed(svc):
    make_issue(svc.jobs, "j20261115_150000_aaaa")
    p = svc.jobs / "j20261115_150000_aaaa" / "job.json"
    d = json.loads(p.read_text())
    d["log"][0]["at"] = "yesterday"
    p.write_text(json.dumps(d))
    assert svc.confirm(svc.prepare(**NEW)[1]["token"])[0] == 503


# ---- the POST gates (11.1, 11.10) -----------------------------------------------------------------------------------------

@pytest.mark.parametrize("path", ["/api/prepare", "/api/confirm"])
class TestGates:
    def test_a_foreign_host(self, svc, path):
        for host in ("localhost:8712", "127.0.0.1:8711", "evil.example", "127.0.0.1:8710"):
            assert svc.request("POST", path, NEW, host=host)[0] == 421

    def test_the_origin_must_be_the_chats_own(self, svc, path):
        for origin in (None, "http://localhost:8712", "http://127.0.0.1:8710", "http://localhost:8710", "http://127.0.0.1:8711",
                       "null", "https://127.0.0.1:8712", "http://evil.example"):
            assert svc.request("POST", path, NEW, headers={"Origin": origin})[0] == 403

    def test_sec_fetch_site(self, svc, path):
        for site in ("same-site", "cross-site"):
            assert svc.request("POST", path, NEW, headers={"Sec-Fetch-Site": site})[0] == 403

    def test_the_body_must_be_json(self, svc, path):
        for ctype in ("application/x-www-form-urlencoded", "text/plain", "application/json; charset=utf-8", "multipart/form-data", None):
            assert svc.request("POST", path, NEW, headers={"Content-Type": ctype})[0] == 415

    def test_the_length(self, svc, path):
        assert svc.request("POST", path, raw=b"x" * (ca.BODY_MAX + 1))[0] == 413
        assert svc.request("POST", path, raw=b"", headers={"Content-Length": "0"})[0] == 413
        assert svc.request("POST", path, raw=b"{}", headers={"Content-Length": "abc"})[0] == 411

    def test_bad_json(self, svc, path):
        for raw in (b"{", b"[]", b'"x"', b"null", b'{"a": 1, "a": 2}', b'{"action": "issue_new", "action": "issue_start"}', b"\xff\xfe"):
            assert svc.request("POST", path, raw=raw)[0] == 400

    def test_nothing_ran(self, svc, path):
        svc.request("POST", path, NEW, host="evil.example")
        svc.request("POST", path, raw=b'{"action": "issue_new", "action": "x"}')
        assert svc.spawner.calls == [] and svc.runs == []


@pytest.mark.parametrize("method, path", [("POST", "/api/threads"), ("POST", "/api/status"), ("POST", "/api/issues"), ("POST", "/"),
                                          ("PUT", "/api/prepare"), ("DELETE", "/api/confirm"), ("PATCH", "/api/prepare"),
                                          ("OPTIONS", "/api/prepare"), ("HEAD", "/api/confirm"), ("GET", "/api/prepare")])
def test_only_the_two_post_routes_take_a_post(svc, method, path):
    status, _ = svc.request(method, path, NEW if method == "POST" else None)
    assert status in (405, 404) and svc.spawner.calls == []
    if method != "GET":
        assert status == 405


def test_a_read_only_chat_still_refuses_every_post(tmp_path):
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    chat = rc.Chat(jobs)
    srv = rc.server(chat, port=0)
    threading.Thread(target=lambda: srv.serve_forever(poll_interval=0.01), daemon=True).start()
    try:
        c = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=5)
        c.request("POST", "/api/prepare", b"{}", {"Host": HOST, "Origin": ORIGIN, "Content-Type": "application/json"})
        assert c.getresponse().status == 405
    finally:
        srv.shutdown()
        srv.server_close()


# ---- audit (11.14) ---------------------------------------------------------------------------------------------------------

def test_one_line_per_prepare_and_confirm_without_the_token_or_the_text(svc):
    out = svc.prepare(**NEW)[1]
    token = out["token"]
    svc.confirm(token)
    lines = svc.audit()
    assert [x.get("ok") or x.get("attempt") for x in lines] == ["prepare", "confirm", "confirm"]
    raw = svc.actions.audit_path.read_text()
    assert token not in raw and NEW["message"] not in raw and WKEY not in raw and KEY not in raw
    assert lines[0]["digest"] == lines[1]["digest"] and len(lines[0]["digest"]) == 64


def test_a_refused_post_is_audited_with_its_gate(svc):
    svc.request("POST", "/api/prepare", NEW, headers={"Origin": "http://evil.example"})
    svc.request("POST", "/api/prepare", {"action": "issue_new", "repo": "x", "message": "m"})
    assert [x.get("refused") for x in svc.audit()] == ["origin", "form"]


def test_when_the_audit_cannot_be_written_nothing_runs(svc):
    svc.actions.audit_path.mkdir(parents=True)                       # a directory where the file should be
    assert svc.prepare(**NEW)[0] == 503
    token = next(iter(svc.actions.prepared), None)
    assert token is None or svc.spawner.calls == []
    assert svc.spawner.calls == [] and svc.runs == []


# ---- reading an issue job -------------------------------------------------------------------------------------------------

def test_the_thread_is_scrubbed_and_hides_what_the_snapshot_hides(svc):
    make_issue(svc.jobs, JOB, conversation=[
        {"from": "human", "text": "do ‮this​ now"},
        {"from": "writer", "text": "token sk-ant-api03-AAAAAAAAAAAAAAAAAAAA", "questions": ["which page?‮"], "clashes": []}])
    status, d = svc.request("GET", f"/api/issues/{JOB}")
    assert status == 200 and d["conversation"][0]["text"] == "do this now" and d["turn"] == 2
    assert "withheld" in d["conversation"][1]["text"] and "sk-ant" not in json.dumps(d)
    assert d["conversation"][1]["questions"] == ["which page?"] and d["repo"] == "argus-viewer"
    assert "/secret/path" not in json.dumps(d) and d["busy"] is False and d["issue"]["sha12"]


def test_the_list_and_a_missing_or_foreign_job(svc):
    make_issue(svc.jobs, JOB)
    assert [i["id"] for i in svc.request("GET", "/api/issues")[1]["issues"]] == [JOB]
    assert svc.request("GET", "/api/issues/j20261115_235959_ffff")[0] == 404
    assert svc.request("GET", "/api/issues/..")[0] == 404


def test_a_symlinked_job_directory_is_never_read(svc, tmp_path):
    secret = tmp_path / "secret"
    secret.mkdir()
    make_issue(tmp_path / "elsewhere", "j20261115_210000_cafe")
    os.symlink(tmp_path / "elsewhere" / "j20261115_210000_cafe", svc.jobs / "j20261115_210000_cafe")
    assert svc.request("GET", "/api/issues/j20261115_210000_cafe")[0] == 404
    assert svc.prepare(action="issue_start", job="j20261115_210000_cafe")[0] == 404


def test_the_get_routes_keep_the_host_and_fetch_checks(svc):
    make_issue(svc.jobs, JOB)
    for path in ("/api/issues", f"/api/issues/{JOB}"):
        assert svc.request("GET", path, host="evil.example")[0] == 421
        assert svc.request("GET", path, headers={"Sec-Fetch-Site": "same-site"})[0] == 403


def test_the_chat_module_still_holds_no_process_and_no_model():
    src = Path(rc.__file__).read_text()
    assert "subprocess" not in src and "Popen" not in src and "harness.llm" not in src


def test_a_job_id_cannot_walk_out_of_the_jobs_directory(svc, tmp_path):
    make_issue(tmp_path / "elsewhere", "j20261115_210000_cafe")
    (tmp_path / "job.json").write_text(json.dumps({"job": "x", "kind": "issue", "state": ri.AWAITING_HUMAN, "inputs": {"repo_name": "r"}}))
    for j in ("..", "../elsewhere/j20261115_210000_cafe", "../../tmp", "."):
        assert svc.prepare(action="issue_start", job=j)[0] == 404
        assert svc.request("GET", f"/api/issues/{j}")[0] == 404
        assert svc.actions.read_issue(j) is None
