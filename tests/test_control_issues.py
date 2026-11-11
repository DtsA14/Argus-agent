"""The issue writer's pages of the control service (SPEC_ISSUE_WRITER 6, router/control_issues.py): every POST through
the F3 gates, the CLI run in the background with the message in a file and the key file from the environment. A real
server on a free port; the issue job is a real one written by a fake model; the background runs are recorded."""
import json
import os
import re
import stat
import sys
import threading
import time
import http.client
from pathlib import Path
from urllib.parse import urlencode

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_issue_writer as tiw  # noqa: E402

from router import control as rc  # noqa: E402
from router import control_issues as ci  # noqa: E402
from router import issue as ri  # noqa: E402
from router import job as rj  # noqa: E402

JOB = "j20261109_150000_abcd"
ORIGIN = "http://localhost:8711"
KEY = "/nowhere/key-file-path"


class Spawned:
    """A Spawner that records the runs instead of starting them; `busy` is set by a test."""

    def __init__(self, state):
        self.real = ci.Spawner(state)
        self.calls, self.busy_ids, self.outcomes = [], set(), {}

    def busy(self, job_id):
        return job_id in self.busy_ids

    def outcome(self, job_id):
        return None if job_id in self.busy_ids else self.outcomes.get(job_id)

    def message_file(self, text):
        return self.real.message_file(text)

    def spawn(self, job_id, argv, message=None, action="", text=None):
        self.calls.append((job_id, argv, message))
        self.texts = getattr(self, "texts", []) + [(action, text)]


class Svc:
    def __init__(self, tmp_path, key=KEY):
        self.env = tiw.Env(tmp_path, [tiw.SUBMIT])
        self.jobs = self.env.jobs
        self.jobs.mkdir(exist_ok=True)
        self.audit = tmp_path / "audit.jsonl"
        self.runs = []

        def run(action, job_id, reason, sha, jobs_dir):
            self.runs.append((action, job_id, reason, sha))
            return 0, "ok"
        self.control = rc.Control(self.jobs, audit=self.audit, run=run)
        self.spawner = Spawned(tmp_path / "state")
        self.control.issues = ci.IssuePages(self.control, self.env.cfg, spawner=self.spawner,
                                            environ={ci.KEY_ENV: key} if key else {})
        self.srv = rc.server(self.control, port=0)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def stop(self):
        self.srv.shutdown()
        self.srv.server_close()

    def new_job(self):
        return ri.new(repo="demo", message=tiw.FIRST, cfg=self.env.cfg, deps=self.env.deps, jobs_dir=self.jobs,
                      job_id=JOB)

    def request(self, method, path, body=b"", headers=None, host="localhost:8711"):
        c = http.client.HTTPConnection("127.0.0.1", self.srv.server_address[1], timeout=30)
        h = {"Host": host, **(headers or {})}
        if method == "POST":
            h.setdefault("Content-Type", "application/x-www-form-urlencoded")
            h.setdefault("Content-Length", str(len(body)))
        c.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
        for k, v in h.items():
            c.putheader(k, v)
        c.endheaders()
        if body:
            c.send(body)
        r = c.getresponse()
        out = (r.status, dict(r.getheaders()), r.read().decode())
        c.close()
        return out

    def form(self, path, action):
        status, _, text = self.request("GET", path)
        assert status == 200, text
        m = re.search(rf'action="{re.escape(action)}"><input type="hidden" name="token" value="([^"]+)">'
                      r'(?:<input type="hidden" name="sha" value="([^"]*)">)?', text)
        assert m, text
        return m.group(1), m.group(2)

    def post(self, path, fields, headers=None):
        """A form POST; a job's form gets the conversation length it would carry (amendment 1) unless a test sets it."""
        m = re.fullmatch(r"/issues/([^/]+)/[a-z]+", path)
        if m and "turn" not in fields and (self.jobs / m.group(1) / "job.json").exists():
            fields = {**fields, "turn": str(ci.turn_of(rj.open_job(m.group(1), self.jobs)))}
        return self.request("POST", path, urlencode(fields).encode(), {"Origin": ORIGIN, **(headers or {})})

    def audit_lines(self):
        return [json.loads(x) for x in self.audit.read_text().splitlines()] if self.audit.exists() else []


@pytest.fixture
def svc(tmp_path):
    s = Svc(tmp_path)
    yield s
    s.stop()


def new_fields(svc, message="Kartu job\r\ntambahin tanggal", repo="demo"):
    token, _ = svc.form("/issues/new", "/issues/new")
    return {"token": token, "repo": repo, "message": message}


# ---- pages -------------------------------------------------------------------------------------------------------

def test_the_index_lists_issue_jobs_only_and_links_new_issue(svc):
    svc.new_job()
    (svc.jobs / "j20261109_150001_beef").mkdir()
    _, _, text = svc.request("GET", "/issues")
    assert f'/issues/{JOB}' in text and "beef" not in text and 'href="/issues/new"' in text
    assert "Kartu job tambahin" in text
    assert 'href="/issues"' in svc.request("GET", "/")[2]


def test_the_new_page_offers_only_the_configured_repositories(svc):
    _, _, text = svc.request("GET", "/issues/new")
    assert re.findall(r'<option value="([^"]+)"', text) == ["demo"] and "<textarea" in text


def test_without_the_key_file_variable_the_writer_is_not_offered(tmp_path):
    s = Svc(tmp_path, key=None)
    try:
        _, _, text = s.request("GET", "/issues/new")
        assert ci.KEY_ENV in text and "<form" not in text
        s.new_job()
        _, _, page = s.request("GET", f"/issues/{JOB}")
        assert "Start job" not in page and "Your reply" not in page and "Discard" in page
    finally:
        s.stop()


def test_the_job_page_shows_the_conversation_issue_clashes_and_questions_as_text(svc):
    job = svc.new_job()
    job.data["conversation"][0]["text"] = "<script>alert(1)</script>\nbaris dua"
    job.save()
    _, headers, text = svc.request("GET", f"/issues/{JOB}")
    assert "<script>alert" not in text and "&lt;script&gt;alert(1)&lt;/script&gt;\nbaris dua" in text
    assert "clash: src/list.test.js:2 reads the cell" in text and "question: Pakai jam juga?" in text
    assert tiw.ISSUE.splitlines()[0] in text and "Start job" in text and "Send" in text
    assert 'http-equiv="refresh"' not in text and headers["Content-Security-Policy"].startswith("default-src 'none'")


def test_a_busy_or_writing_job_reloads_itself_and_offers_no_action(svc):
    svc.new_job()
    svc.spawner.busy_ids.add(JOB)
    _, _, text = svc.request("GET", f"/issues/{JOB}")
    assert 'http-equiv="refresh" content="3"' in text and "<form" not in text


def test_a_job_of_another_kind_has_no_issue_page(svc):
    job = svc.new_job()
    job.data["kind"] = "code"
    job.save()
    assert svc.request("GET", f"/issues/{JOB}")[0] == 404


# ---- new ---------------------------------------------------------------------------------------------------------

def test_new_runs_the_cli_in_the_background_with_the_message_in_a_file(svc):
    status, _, text = svc.post("/issues/new", new_fields(svc))
    assert status == 200, text
    (job_id, argv, message), = svc.spawner.calls
    assert rc.UI_ID.fullmatch(job_id) and f"/issues/{job_id}" in text
    assert argv[argv.index("issue") + 1] == "new" and argv[argv.index("--repo") + 1] == "demo"
    assert argv[argv.index("--job-id") + 1] == job_id and argv[argv.index("--key-file") + 1] == KEY
    assert argv[-3:] == ["--key-file", KEY, "--yes"] and "--via" in argv and argv[argv.index("--via") + 1] == "ui"
    assert Path(message).read_text() == "Kartu job\ntambahin tanggal"            # CRLF from a textarea, as typed
    assert stat.S_IMODE(os.stat(message).st_mode) == 0o600
    assert not any("tambahin" in a for a in argv)                                 # never in argv
    lines = svc.audit_lines()
    assert [ln.get("attempt") or ln.get("action") for ln in lines] == ["new", "new"]
    assert "tambahin" not in svc.audit.read_text() and "token" not in svc.audit.read_text()


@pytest.mark.parametrize("fields, why", [
    ({"repo": "other"}, "is not one the writer reads"),
    ({"repo": "../demo"}, "is not one the writer reads"),
    ({"message": ""}, "empty"),
    ({"message": "a‮b"}, "control"),
    ({"message": "x" * 4001}, "more than 4000"),
])
def test_a_bad_new_form_is_refused_before_the_token_and_keeps_what_was_typed(svc, fields, why):
    f = {**new_fields(svc, message="tetap ada"), **fields}
    status, _, text = svc.post("/issues/new", f)
    assert status == 400 and why in text and svc.spawner.calls == []
    if "message" not in fields:
        assert ">tetap ada</textarea>" in text
    assert svc.post("/issues/new", {**f, "repo": "demo", "message": "sekarang benar"})[0] == 200


@pytest.mark.parametrize("headers", [{"Origin": "http://evil.example"}, {"Origin": "null"},
                                     {"Sec-Fetch-Site": "cross-site"}])
def test_new_from_another_origin_is_refused(svc, headers):
    status, _, _ = svc.post("/issues/new", new_fields(svc), headers)
    assert status == 403 and svc.spawner.calls == [] and svc.audit_lines()[-1]["refused"] == "origin"


def test_new_without_its_token_or_twice_is_refused(svc):
    f = new_fields(svc)
    assert svc.post("/issues/new", {**f, "token": ""})[0] == 403
    assert svc.post("/issues/new", f)[0] == 200
    assert svc.post("/issues/new", f)[0] == 403 and len(svc.spawner.calls) == 1


def test_new_without_the_key_file_variable_is_refused(tmp_path):
    s = Svc(tmp_path)
    try:
        f = new_fields(s)
        s.control.issues.environ = {}
        status, _, text = s.post("/issues/new", f)
        assert status == 409 and ci.KEY_ENV in text and s.spawner.calls == []
    finally:
        s.stop()


def test_a_long_message_in_another_script_fits_and_a_larger_body_is_refused(svc):
    f = new_fields(svc, message="😀" * 4000)                   # 48,000 bytes once percent-encoded
    assert len(urlencode(f)) > rc.BODY_MAX
    assert svc.post("/issues/new", f)[0] == 200
    big = urlencode({**new_fields(svc), "message": "x" * 70000}).encode()
    assert svc.request("POST", "/issues/new", big, {"Origin": ORIGIN})[0] == 413
    assert len(svc.spawner.calls) == 1


# ---- reply, start, abandon ---------------------------------------------------------------------------------------

def test_reply_runs_in_the_background_with_its_file_and_the_job_after_the_separator(svc):
    svc.new_job()
    token, sha = svc.form(f"/issues/{JOB}", f"/issues/{JOB}/reply")
    status, _, _ = svc.post(f"/issues/{JOB}/reply", {"token": token, "sha": sha, "message": "Pakai jam"})
    assert status == 200
    (job_id, argv, message), = svc.spawner.calls
    assert job_id == JOB and argv[argv.index("issue") + 1] == "reply" and argv[-2:] == ["--", JOB]
    assert Path(message).read_text() == "Pakai jam"


def test_start_names_the_sha_shown_and_is_refused_once_the_issue_changed(svc):
    job = svc.new_job()
    token, sha = svc.form(f"/issues/{JOB}", f"/issues/{JOB}/start")
    assert sha == job.data["issue_sha256"][:12]
    job.data["issue_sha256"] = "f" * 64                       # another turn wrote another issue meanwhile
    job.save()
    status, _, text = svc.post(f"/issues/{JOB}/start", {"token": token, "sha": sha})
    assert status == 409 and "issue changed" in text and svc.spawner.calls == []
    job.data["issue_sha256"] = ri.last_issue(job)[1]
    job.save()
    token, sha = svc.form(f"/issues/{JOB}", f"/issues/{JOB}/start")
    assert svc.post(f"/issues/{JOB}/start", {"token": token, "sha": sha})[0] == 200
    (_, argv, message), = svc.spawner.calls
    assert argv[argv.index("start") + 1:argv.index("start") + 3] == ["--sha", sha] and argv[-2:] == ["--", JOB]
    assert message is None


def test_a_token_is_bound_to_its_action(svc):
    svc.new_job()
    reply_token, sha = svc.form(f"/issues/{JOB}", f"/issues/{JOB}/reply")
    assert svc.post(f"/issues/{JOB}/start", {"token": reply_token, "sha": sha})[0] == 403
    assert svc.spawner.calls == []


def test_a_busy_job_takes_no_second_run(svc):
    svc.new_job()
    token, sha = svc.form(f"/issues/{JOB}", f"/issues/{JOB}/reply")
    svc.spawner.busy_ids.add(JOB)
    status, _, text = svc.post(f"/issues/{JOB}/reply", {"token": token, "sha": sha, "message": "lagi"})
    assert status == 409 and "still working" in text and svc.spawner.calls == []


def test_discard_runs_abandon_at_once_with_a_default_reason(svc):
    svc.new_job()
    token, sha = svc.form(f"/issues/{JOB}", f"/issues/{JOB}/abandon")
    status, _, _ = svc.post(f"/issues/{JOB}/abandon", {"token": token, "sha": sha, "reason": ""})
    assert status == 200 and svc.runs == [("abandon", JOB, "discarded from the phone", "")]


def test_a_handed_off_job_links_its_code_job_and_offers_nothing(svc):
    job = svc.new_job()
    job.data["state"], job.data["handoff"] = ri.HANDED_OFF, {"job": "j20261109_150002_cafe"}
    job.save()
    _, _, text = svc.request("GET", f"/issues/{JOB}")
    assert "j20261109_150002_cafe/draft" in text and 'href="/jobs/j20261109_150002_cafe"' in text and "<form" not in text


@pytest.mark.parametrize("path", ["/issues/..%2Fx/reply", "/issues/jtest/reply", f"/issues/{JOB}/approve",
                                  "/issues/new/x"])
def test_an_unknown_issue_path_is_refused(svc, path):
    svc.new_job()
    status, _, _ = svc.request("POST", path, b"token=x&sha=&message=m", {"Origin": ORIGIN})
    assert status == 404 and svc.spawner.calls == []


# ---- the real spawner --------------------------------------------------------------------------------------------

def test_the_spawner_runs_one_child_per_job_and_removes_its_message_file_after(tmp_path):
    sp = ci.Spawner(tmp_path / "state")
    msg = sp.message_file("halo")
    assert stat.S_IMODE(os.stat(msg).st_mode) == 0o600
    sp.spawn(JOB, [sys.executable, "-c", "import time; time.sleep(0.5)"], msg)
    assert sp.busy(JOB)
    for _ in range(100):
        if not sp.busy(JOB):
            break
        time.sleep(0.05)
    assert not sp.busy(JOB) and not msg.exists() and list((tmp_path / "state" / "runs").glob(f"{JOB}-*.log"))


def test_a_sha_field_changed_with_a_good_token_starts_nothing(svc):
    svc.new_job()
    token, sha = svc.form(f"/issues/{JOB}", f"/issues/{JOB}/start")
    status, _, text = svc.post(f"/issues/{JOB}/start", {"token": token, "sha": "0" * 12})
    assert status == 409 and "issue changed" in text and svc.spawner.calls == []


@pytest.mark.parametrize("reason", ["two\nlines", "bidi‮", "x" * 301])
def test_a_bad_discard_reason_is_refused(svc, reason):
    svc.new_job()
    token, sha = svc.form(f"/issues/{JOB}", f"/issues/{JOB}/abandon")
    status, _, _ = svc.post(f"/issues/{JOB}/abandon", {"token": token, "sha": sha, "reason": reason})
    assert status == 400 and svc.runs == []



# ---- added for /code-review -------------------------------------------------------------------------------------

def test_a_new_job_not_made_yet_shows_starting_then_why_it_could_not_start_with_the_text(svc):
    svc.post("/issues/new", new_fields(svc, message="mau fitur X"))
    (job_id, _, _), = svc.spawner.calls
    svc.spawner.busy_ids.add(job_id)
    status, _, text = svc.request("GET", f"/issues/{job_id}")
    assert status == 200 and "Starting the writer" in text and 'http-equiv="refresh"' in text
    svc.spawner.busy_ids.discard(job_id)
    svc.spawner.outcomes[job_id] = {"code": 2, "line": "issue writer (role 'x'): not priced", "action": "new",
                                    "text": "mau fitur X"}
    status, _, text = svc.request("GET", f"/issues/{job_id}")
    assert status == 200 and "could not start: issue writer" in text and ">mau fitur X</textarea>" in text
    assert svc.request("GET", "/issues/j20261109_150009_ffff")[0] == 404        # a job no run knows of


def test_a_refused_background_reply_says_why_and_gives_the_text_back(svc):
    svc.new_job()
    svc.spawner.outcomes[JOB] = {"code": 2, "line": "less than one turn", "action": "reply", "text": "balasanku"}
    _, _, text = svc.request("GET", f"/issues/{JOB}")
    assert "the last reply was refused: less than one turn" in text and ">balasanku</textarea>" in text


def test_discard_is_not_offered_or_taken_while_a_cut_off_start_holds_a_code_job(svc, monkeypatch):
    job = svc.new_job()
    job.data["handoff"] = {"job": "j20261109_150003_dead"}
    job.save()
    from types import SimpleNamespace
    monkeypatch.setattr(ri, "_handed", lambda j, d: SimpleNamespace(id="j20261109_150003_dead"))
    _, _, text = svc.request("GET", f"/issues/{JOB}")
    assert "A start was cut off" in text and "Discard" not in text
    with pytest.raises(rj.Refused, match="a start was cut off"):
        rj.abandon(JOB, "x", deps=svc.env.deps, jobs_dir=svc.jobs)


def test_a_refused_discard_has_one_refused(svc):
    svc.new_job()
    svc.control.run = lambda *a: (2, "refused: job j is in use by another command")
    token, sha = svc.form(f"/issues/{JOB}", f"/issues/{JOB}/abandon")
    _, _, text = svc.post(f"/issues/{JOB}/abandon", {"token": token, "sha": sha, "reason": ""})
    assert "refused: job j is in use" in text and "refused: refused" not in text


@pytest.mark.parametrize("value", [None, "big", True, 10])
def test_a_body_limit_missing_or_wrong_falls_back_and_never_crashes(svc, value):
    svc.control.issues.cfg = {**svc.env.cfg, "control": value if value is None else {"message_body_max": value}}
    assert svc.control.issues.body_max() == rc.BODY_MAX
    status, _, _ = svc.post("/issues/new", new_fields(svc))
    assert status == 200


def test_the_real_spawner_keeps_a_refused_runs_reason_and_text_and_reaps_every_run(tmp_path):
    sp = ci.Spawner(tmp_path / "state")
    msg = sp.message_file("teksku")
    sp.spawn(JOB, [sys.executable, "-c", "print('refused: no budget'); raise SystemExit(2)"], msg, action="reply",
             text="teksku")
    other = "j20261109_150004_aaaa"
    sp.spawn(other, [sys.executable, "-c", "pass"], sp.message_file("x"), action="new", text="x")
    for _ in range(100):
        sp.reap()
        if not sp.runs:
            break
        time.sleep(0.05)
    assert sp.runs == {} and list((tmp_path / "state" / "messages").glob("*.txt")) == []
    assert sp.outcome(JOB) == {"code": 2, "line": "no budget", "action": "reply", "text": "teksku"}
    assert sp.outcome(other)["text"] is None                  # a run that was not refused keeps no text


def test_message_files_a_restart_left_behind_are_removed_once_stale(tmp_path):
    d = tmp_path / "state" / "messages"
    d.mkdir(parents=True)
    old, fresh = d / "old.txt", d / "fresh.txt"
    old.write_text("a")
    fresh.write_text("b")
    os.utime(old, (time.time() - 3600, time.time() - 3600))
    ci.Spawner(tmp_path / "state")
    assert not old.exists() and fresh.exists()


def test_the_index_reads_only_the_newest_job_directories(svc, monkeypatch):
    monkeypatch.setattr(ci, "INDEX_MAX", 1)
    svc.new_job()
    (svc.jobs / "j20991231_235959_ffff").mkdir()               # newer, not an issue job
    _, _, text = svc.request("GET", "/issues")
    assert JOB not in text


# ---- amendment 1: the steps of a running turn, a reply without an issue, the chat --------------------------------

def _running(svc, lines):
    job = svc.new_job()
    job.data["state"] = ri.WRITING
    job.data["stages"]["w2"] = {"kind": "write", "run_id": f"{JOB}-w2", "cap_usd": 0.1,
                                "started_at": "2026-11-09T12:00:00Z"}
    job.save()
    if lines is not None:
        d = job.runs / f"{JOB}-w2"
        d.mkdir(parents=True)
        (d / "events.jsonl").write_text("\n".join(lines) + "\n")
    return job


def step(tool, target):
    return json.dumps({"ts": 1.0, "event": "writer_step", "tool": tool, "target": target})


def test_a_running_turn_shows_its_steps_as_text_and_reloads(svc):
    lines = [step("ListFiles", ""), "{broken", json.dumps({"event": "tool_call", "tool": "read_file"}),
             step("ReadFile", "src/<img src=x onerror=alert(1)>.js"), step("SearchFiles", "expect(")]
    lines += [step("ReadFile", f"src/f{i}.js") for i in range(ci.STEPS_SHOWN)]
    _running(svc, lines)
    svc.spawner.busy_ids.add(JOB)
    status, _, text = svc.request("GET", f"/issues/{JOB}")
    assert status == 200 and 'http-equiv="refresh" content="3"' in text and "<form" not in text
    shown = re.findall(r'<li><span class="dot"></span>(.*?)</li>', text)
    assert len(shown) == ci.STEPS_SHOWN and "src/f0.js" in shown[0] and f"src/f{ci.STEPS_SHOWN - 1}.js" in shown[-1]
    assert "Working… (" in text


def test_the_steps_are_escaped_and_a_broken_or_missing_log_still_shows_the_page(svc):
    job = _running(svc, [step("ReadFile", "<img src=x onerror=alert(1)>"), "{broken"])
    svc.spawner.busy_ids.add(JOB)
    _, _, text = svc.request("GET", f"/issues/{JOB}")
    assert "<img src=x" not in text and "Reading <span class=\"mono\">&lt;img src=x onerror=alert(1)&gt;" in text
    (job.runs / f"{JOB}-w2" / "events.jsonl").unlink()
    status, _, text = svc.request("GET", f"/issues/{JOB}")
    assert status == 200 and "Working…" in text and '<span class="dot">' not in text


def test_the_steps_come_from_the_end_of_a_long_log(svc, monkeypatch):
    monkeypatch.setattr(ci, "EVENTS_TAIL", 400)
    lines = [step("ReadFile", "early.js")] + [json.dumps({"event": "pad", "x": "y" * 50})] * 20 + \
        [step("ReadFile", "late.js")]
    _running(svc, lines)
    steps, _ = ci.turn_steps(rj.open_job(JOB, svc.jobs))
    assert steps == [("ReadFile", "late.js")]


def test_a_writing_job_no_run_works_on_says_how_to_resume(svc):
    _running(svc, [step("ReadFile", "a.js")])
    _, _, text = svc.request("GET", f"/issues/{JOB}")
    assert "No run of this service is working on it" in text and f"argus resume {JOB}" in text
    assert "Working…" not in text and 'http-equiv="refresh"' in text


@pytest.mark.parametrize("action", ["start", "reply", "abandon"])
def test_a_page_opened_before_a_reply_without_an_issue_is_refused(svc, action):
    job = svc.new_job()
    token, sha = svc.form(f"/issues/{JOB}", f"/issues/{JOB}/{action}")
    job.data["conversation"] += [{"from": "human", "at": "t", "text": "kenapa?"},
                                 {"from": "writer", "at": "t", "stage": "w2", "text": "Karena WIB.", "clashes": [],
                                  "questions": []}]
    job.save()
    fields = {"token": token, "sha": sha, "turn": "2", **({"message": "ok"} if action == "reply" else {}),
              **({"reason": ""} if action == "abandon" else {})}
    status, _, text = svc.post(f"/issues/{JOB}/{action}", fields)
    assert status == 409 and "the writer answered since the page was opened" in text and svc.spawner.calls == []
    assert svc.runs == []
    fields["turn"] = "4"                                   # the length now, with the old page's token
    assert svc.post(f"/issues/{JOB}/{action}", fields)[0] == 403


def test_the_turn_seconds_come_from_its_start():
    class J:
        data = {"stages": {"w1": {"kind": "write", "status": "WRITTEN", "run_id": "r1"},
                           "w2": {"kind": "write", "run_id": "r2", "started_at": "2026-11-09T12:00:00Z"}}}
        runs = Path("/nowhere")
    steps, seconds = ci.turn_steps(J(), now=1794225600 + 17)
    assert steps == [] and seconds == 17
    J.data["stages"]["w2"]["status"] = "WRITTEN"
    assert ci.turn_steps(J()) is None


def test_a_reply_without_an_issue_offers_no_start_until_an_issue_exists(tmp_path):
    s = Svc(tmp_path)
    s.env.model = tiw.StrictScriptedChatModel(script=[tiw.ONLY])
    s.env.deps.models["issue_writer"] = s.env.model
    try:
        s.new_job()
        _, _, text = s.request("GET", f"/issues/{JOB}")
        assert tiw.ANSWER in text and "Start job" not in text and "/start" not in text and "ISSUE ·" not in text
        assert "Your reply" in text and "Discard" in text
    finally:
        s.stop()


def test_the_chat_shows_the_human_as_bubbles_and_the_issue_card_holds_start(svc):
    svc.new_job()
    _, _, text = svc.request("GET", f"/issues/{JOB}")
    assert f'<div class="bubble"><p class="text">{tiw.FIRST}</p></div>' in text
    card = text[text.index('<section class="card issue">'):]
    card = card[:card.index("</section>")]
    assert tiw.ISSUE.splitlines()[0] in card and f'action="/issues/{JOB}/start"' in card


# ---- amendment 5: the writer's own key file ----------------------------------------------------------------------

WRITER_KEY = "/nowhere/writer-key-file-path"


def test_the_writer_turns_take_the_writer_key_file_and_start_the_code_job_one(svc):
    svc.control.issues.environ = {ci.KEY_ENV: KEY, ci.WRITER_KEY_ENV: WRITER_KEY}
    assert svc.post("/issues/new", new_fields(svc))[0] == 200
    svc.new_job()
    token, sha = svc.form(f"/issues/{JOB}", f"/issues/{JOB}/reply")
    assert svc.post(f"/issues/{JOB}/reply", {"token": token, "sha": sha, "message": "Pakai jam"})[0] == 200
    token, sha = svc.form(f"/issues/{JOB}", f"/issues/{JOB}/start")
    assert svc.post(f"/issues/{JOB}/start", {"token": token, "sha": sha})[0] == 200
    keys = [argv[argv.index("--key-file") + 1] for _, argv, _ in svc.spawner.calls]
    assert keys == [WRITER_KEY, WRITER_KEY, KEY]


def test_with_only_the_writer_key_file_the_writer_runs_and_start_is_neither_offered_nor_taken(svc):
    svc.control.issues.environ = {ci.WRITER_KEY_ENV: WRITER_KEY}
    assert svc.post("/issues/new", new_fields(svc))[0] == 200
    svc.new_job()
    text = svc.request("GET", f"/issues/{JOB}")[2]
    assert f'action="/issues/{JOB}/reply"' in text and f'action="/issues/{JOB}/start"' not in text
    svc.control.issues.environ = {ci.KEY_ENV: KEY, ci.WRITER_KEY_ENV: WRITER_KEY}
    token, sha = svc.form(f"/issues/{JOB}", f"/issues/{JOB}/start")
    svc.control.issues.environ = {ci.WRITER_KEY_ENV: WRITER_KEY}
    status, _, text = svc.post(f"/issues/{JOB}/start", {"token": token, "sha": sha})
    assert status == 409 and ci.KEY_ENV in text and len(svc.spawner.calls) == 1


def test_an_empty_writer_key_variable_falls_back_to_the_key_file(svc):
    svc.control.issues.environ = {ci.KEY_ENV: KEY, ci.WRITER_KEY_ENV: ""}
    assert svc.post("/issues/new", new_fields(svc))[0] == 200
    (_, argv, _), = svc.spawner.calls
    assert argv[argv.index("--key-file") + 1] == KEY
