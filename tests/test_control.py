"""The phone's control service, phase 2 (docs/reviews/SPEC_CONTROL_UI.md 4a, F9): every gate refuses before the CLI,
and the CLI's own gates (state, lock, draft sha) hold through it. A real server on a free port; the CLI is the real
`scripts/argus.py` where its gates are under test."""
import http.client
import json
import re
import threading

import pytest

from router import control as rc
from router import job as rj

JOB = "j20261109_120000_abcd"
ORIGIN = "http://localhost:8711"
DRAFT = {"draft_version": 1, "plan": {"files": ["a.py"]}, "note": "<img src=x onerror=alert(1)>"}


def make_job(jobs, job_id=JOB, state=rj.AWAITING_APPROVAL, draft=DRAFT):
    d = jobs / job_id
    (d / "runs" / f"{job_id}-d1").mkdir(parents=True)
    stages = {}
    if draft is not None:
        (d / "runs" / f"{job_id}-d1" / "draft.json").write_text(json.dumps(draft), encoding="utf-8")
        stages["d1"] = {"kind": "draft", "status": "DRAFTED", "run_id": f"{job_id}-d1"}
    (d / "job.json").write_text(json.dumps({"job": job_id, "kind": "code", "state": state, "max_usd": 1.0,
                                            "created_at": "2026-11-09T12:00:00Z", "stages": stages, "log": [],
                                            "inputs": {"repo": "/nowhere", "commit": "HEAD", "issue": "t"}}),
                                encoding="utf-8")
    return d


def sha12(jobs, job_id=JOB):
    return rj.draft_sha(jobs / job_id / "runs" / f"{job_id}-d1" / "draft.json")[:12]


class Calls:
    def __init__(self):
        self.calls = []

    def __call__(self, action, job_id, reason, sha, jobs_dir):
        self.calls.append((action, job_id, reason, sha))
        return 0, "ok"


@pytest.fixture
def svc(tmp_path):
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    s = Service(jobs, tmp_path / "audit.jsonl", Calls())
    yield s
    s.stop()


class Service:
    def __init__(self, jobs, audit, run, clock=None):
        self.jobs, self.audit = jobs, audit
        self.control = rc.Control(jobs, audit=audit, run=run, **({"clock": clock} if clock else {}))
        self.run = run
        self.srv = rc.server(self.control, port=0)
        self.port = self.srv.server_address[1]
        self.thread = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        self.srv.shutdown()
        self.srv.server_close()

    def request(self, method, path, body=b"", headers=None, host="localhost:8711"):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
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

    def form(self, job_id=JOB, action="reject"):
        """The token and sha the job's page issued for an action."""
        status, _, text = self.request("GET", f"/jobs/{job_id}")
        assert status == 200, text
        m = re.search(rf'action="/jobs/{job_id}/{action}"><input type="hidden" name="token" value="([^"]+)">'
                      r'<input type="hidden" name="sha" value="([^"]*)">', text)
        assert m, text
        return m.group(1), m.group(2)

    def post(self, action="reject", job_id=JOB, token=None, sha=None, reason="tests look wrong", headers=None,
             body=None, host="localhost:8711"):
        if token is None or sha is None:
            t, s = self.form(job_id, action)
            token, sha = token if token is not None else t, sha if sha is not None else s
        from urllib.parse import urlencode
        body = body if body is not None else urlencode({"token": token, "sha": sha, "reason": reason}).encode()
        return self.request("POST", f"/jobs/{job_id}/{action}", body, {"Origin": ORIGIN, **(headers or {})}, host)

    def audit_lines(self):
        return [json.loads(x) for x in self.audit.read_text().splitlines()] if self.audit.exists() else []


def test_it_binds_127_0_0_1_on_8711_only(svc):
    assert (rc.BIND, rc.PORT) == ("127.0.0.1", 8711)
    assert svc.srv.server_address[0] == "127.0.0.1"


def test_a_good_post_runs_the_cli_once_with_the_sha_seen_and_is_audited(svc):
    make_job(svc.jobs)
    status, _, text = svc.post()
    assert status == 200 and "rejected" in text
    assert svc.run.calls == [("reject", JOB, "tests look wrong", sha12(svc.jobs))]
    attempt, rec = svc.audit_lines()                         # the attempt is written before the job changes (F5)
    assert attempt["attempt"] == "reject" and "exit" not in attempt
    assert rec["action"] == "reject" and rec["exit"] == 0 and rec["job"] == JOB and rec["sha"] == sha12(svc.jobs)


@pytest.mark.parametrize("host", ["evil.example:8711", "127.0.0.1:8710", "localhost", "127.0.0.1"])
def test_a_foreign_host_is_refused_on_get_and_post(svc, host):
    make_job(svc.jobs)
    token, sha = svc.form()
    assert svc.request("GET", f"/jobs/{JOB}", host=host)[0] == 421
    assert svc.post(token=token, sha=sha, host=host)[0] == 421
    assert svc.run.calls == [] and svc.audit_lines()[-1]["refused"] == "host"


@pytest.mark.parametrize("headers", [{"Origin": None}, {"Origin": "null"}, {"Origin": "http://evil.example"},
                                     {"Origin": "http://localhost:8710"}, {"Origin": "https://localhost:8711"},
                                     {"Sec-Fetch-Site": "cross-site"}, {"Sec-Fetch-Site": "same-site"}])
def test_a_post_from_another_origin_is_refused(svc, headers):
    make_job(svc.jobs)
    token, sha = svc.form()
    h = {k: v for k, v in headers.items() if v is not None}
    from urllib.parse import urlencode
    body = urlencode({"token": token, "sha": sha, "reason": "x"}).encode()
    hdrs = {"Origin": ORIGIN, **h}
    if headers.get("Origin", "") is None:
        del hdrs["Origin"]
    status, _, _ = svc.request("POST", f"/jobs/{JOB}/reject", body, hdrs)
    assert status == 403 and svc.run.calls == []
    assert svc.audit_lines()[-1]["refused"] == "origin"


def test_the_pages_let_the_browser_send_its_origin_on_a_form(svc):
    """control p1: with `Referrer-Policy: no-referrer` Safari sent `Origin: null` on the page's own form, and every
    reject from the phone was refused at F3.2. same-origin (or a policy that keeps the origin) is required."""
    make_job(svc.jobs)
    _, headers, _ = svc.request("GET", f"/jobs/{JOB}")
    assert headers["Referrer-Policy"] == "same-origin"


def test_a_refused_origin_is_named_in_the_audit(svc):
    make_job(svc.jobs)
    token, sha = svc.form()
    svc.post(token=token, sha=sha, headers={"Origin": "null"})
    svc.request("POST", f"/jobs/{JOB}/reject", f"token={token}&sha={sha}&reason=x".encode(), {})
    *_, null, missing = svc.audit_lines()
    assert (null["refused"], null["origin"]) == ("origin", "null")
    assert (missing["refused"], missing["origin"]) == ("origin", None)
    assert svc.run.calls == []


def test_tokens_are_bound_to_page_action_and_job_and_spent_once(svc):
    make_job(svc.jobs)
    other = "j20261109_120001_beef"
    make_job(svc.jobs, other)
    token, sha = svc.form(action="reject")
    abandon_token, _ = svc.form(action="abandon")
    other_token, other_sha = svc.form(other, "reject")
    for t, s, job in [("", sha, JOB), ("1.abc", sha, JOB), ("123." + "0" * 64, sha, JOB),
                      (abandon_token, sha, JOB),            # another action's token
                      (other_token, sha, JOB),              # another job's token
                      (token, other_sha, JOB) if other_sha != sha else (token, "0" * 12, JOB)]:   # another sha
        status, _, text = svc.post(token=t, sha=s, job_id=job)
        assert status == 403 and "refused" in text, (t, text)
    assert svc.run.calls == []
    assert svc.post(token=token, sha=sha)[0] == 200
    status, _, text = svc.post(token=token, sha=sha)            # the same page sent twice
    assert status == 403 and "already sent" in text and len(svc.run.calls) == 1
    assert all("token" not in rec or rec.get("refused") == "token" for rec in svc.audit_lines())
    assert token not in svc.audit.read_text() and token.split(".")[1] not in svc.audit.read_text()


def test_an_old_page_is_refused(tmp_path):
    now = [1_800_000_000.0]
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    make_job(jobs)
    s = Service(jobs, tmp_path / "a.jsonl", Calls(), clock=lambda: now[0])
    try:
        token, sha = s.form()
        now[0] += rc.TOKEN_TTL + 1
        status, _, text = s.post(token=token, sha=sha)
        assert status == 403 and "too old" in text and s.run.calls == []
        token, sha = s.form()
        now[0] += rc.TOKEN_TTL - 1
        assert s.post(token=token, sha=sha)[0] == 200
    finally:
        s.stop()


def test_a_token_of_a_restarted_service_is_refused(tmp_path):
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    make_job(jobs)
    first = Service(jobs, tmp_path / "a.jsonl", Calls())
    token, sha = first.form()
    first.stop()
    second = Service(jobs, tmp_path / "a.jsonl", Calls())
    try:
        assert second.post(token=token, sha=sha)[0] == 403 and second.run.calls == []
    finally:
        second.stop()


def test_get_never_changes_a_job(svc):
    make_job(svc.jobs)
    before = (svc.jobs / JOB / "job.json").read_bytes()
    for path in ("/", f"/jobs/{JOB}", f"/jobs/{JOB}/reject", f"/jobs/{JOB}/abandon", "/style.css"):
        svc.request("GET", path)
    assert (svc.jobs / JOB / "job.json").read_bytes() == before and svc.run.calls == [] and svc.audit_lines() == []


@pytest.mark.parametrize("path", ["/jobs/..", "/jobs/%2E%2E", "/jobs/..%2Fjobs", "/jobs/j1", "/jobs/jtest",
                                  f"/jobs/{JOB}%2F..", f"/jobs/{JOB.upper()}", "/jobs/", "/etc/passwd"])
def test_an_id_outside_the_shape_is_404(svc, path):
    make_job(svc.jobs)
    assert svc.request("GET", path)[0] == 404
    status, _, _ = svc.request("POST", path + "/reject", b"token=x&sha=&reason=x", {"Origin": ORIGIN})
    assert status == 404 and svc.run.calls == []


def test_a_job_whose_id_is_not_the_ui_shape_is_404_even_when_it_exists(svc):
    make_job(svc.jobs, "jtest")                              # a valid job id for the CLI, not the shape `code` makes
    assert svc.request("GET", "/jobs/jtest")[0] == 404
    status, _, _ = svc.request("POST", "/jobs/jtest/reject", b"token=x&sha=&reason=x", {"Origin": ORIGIN})
    assert status == 404 and svc.run.calls == [] and "jtest" not in svc.request("GET", "/")[2]


@pytest.mark.parametrize("reason, why", [("", "required"), ("   ", "required"), ("x" * 301, "more than 300"),
                                         ("one\ntwo", "one line"), ("tab\there", "one line"),
                                         ("bell\x07", "one line"), ("c1\x85", "one line"),
                                         ("ok\u2028state: APPLIED", "one line"), ("para\u2029x", "one line"),
                                         ("bidi\u202eevil", "one line"), ("zw\u200bj", "one line")])
def test_a_bad_reason_is_refused_before_the_cli(svc, reason, why):
    make_job(svc.jobs)
    status, _, text = svc.post(reason=reason)
    assert status == 400 and why in text and svc.run.calls == []


def test_a_refused_reason_keeps_the_token_and_what_was_typed(svc):
    make_job(svc.jobs)
    token, sha = svc.form()
    status, _, text = svc.post(token=token, sha=sha, reason="x" * 301)
    assert status == 400 and 'value="' + "x" * 301 + '"' in text
    assert svc.post(token=token, sha=sha, reason="fine")[0] == 200


def test_a_token_written_another_way_is_not_a_new_token(svc):
    make_job(svc.jobs)
    other = "j20261109_120001_beef"
    make_job(svc.jobs, other)
    token, sha = svc.form()
    assert svc.post(token=token, sha=sha)[0] == 200
    issued, mac = token.split(".")
    for t in ("0" + token, f"{issued}.{mac.upper()}", f"+{issued}.{mac}", f"{'٠' + issued}.{mac}"):
        status, _, _ = svc.post(token=t, sha=sha)
        assert status == 403
    assert len(svc.run.calls) == 1


def test_a_page_opened_before_the_draft_cannot_act_on_the_draft(svc):
    make_job(svc.jobs, state=rj.DRAFTING, draft=None)
    token, sha = svc.form(action="abandon")
    assert sha == ""
    run = svc.jobs / JOB / "runs" / f"{JOB}-d1"
    (run / "draft.json").write_text(json.dumps(DRAFT))
    job = rj.open_job(JOB, svc.jobs)
    job.data["stages"]["d1"] = {"kind": "draft", "status": "DRAFTED", "run_id": f"{JOB}-d1"}
    job.data["state"] = rj.AWAITING_APPROVAL
    job.save()
    status, _, text = svc.post("abandon", token=token, sha=sha, reason="")
    assert status == 409 and "draft changed" in text and svc.run.calls == []


def test_an_unreadable_draft_shows_no_form_and_acts_on_nothing(svc):
    make_job(svc.jobs)
    token, sha = svc.form()
    (svc.jobs / JOB / "runs" / f"{JOB}-d1" / "draft.json").write_text("{not json")
    status, _, text = svc.post(token=token, sha=sha)
    assert status == 409 and "cannot be read" in text and svc.run.calls == []
    _, _, page = svc.request("GET", f"/jobs/{JOB}")
    assert "cannot be read" in page and "<form" not in page


def test_a_stalled_client_does_not_hold_the_service():
    assert 0 < rc.Handler.timeout <= 30


def test_abandon_without_a_reason_records_the_default(svc):
    make_job(svc.jobs)
    assert svc.post("abandon", reason="")[0] == 200
    assert svc.run.calls == [("abandon", JOB, rc.ABANDON_DEFAULT, sha12(svc.jobs))]


def test_a_field_sent_twice_or_a_large_body_is_refused(svc):
    make_job(svc.jobs)
    token, sha = svc.form()
    body = f"token={token}&token={token}&sha={sha}&reason=x".encode()
    assert svc.post(body=body)[0] == 400
    big = f"token={token}&sha={sha}&reason=".encode() + b"x" * rc.BODY_MAX
    assert svc.post(body=big)[0] == 413
    assert svc.run.calls == []


def test_too_many_fields_are_refused_and_audited(svc):
    make_job(svc.jobs)
    token, sha = svc.form()
    body = f"token={token}&sha={sha}&reason=x&".encode() + b"&".join(b"f%d=1" % i for i in range(10))
    status, _, text = svc.post(body=body)
    assert status == 400 and "too many fields" in text and svc.run.calls == []
    assert svc.audit_lines()[-1]["refused"] == "form"


def test_the_ui_shape_is_the_whole_segment(svc):
    make_job(svc.jobs, JOB + "\n")                    # a directory the CLI's own id pattern would open
    assert svc.control.job(JOB + "\n") is None and svc.control.job("j٢٠٢٦١١٠٩_120000_abcd") is None


def test_markup_in_a_job_is_text(svc):
    make_job(svc.jobs, state="<script>alert(1)</script>")
    _, _, text = svc.request("GET", f"/jobs/{JOB}")
    assert "<script>alert" not in text and "&lt;script&gt;" in text
    status, _, text = svc.post("abandon", reason="<img src=x onerror=alert(1)>")
    assert "<img" not in text


def test_every_answer_carries_the_security_headers(svc):
    make_job(svc.jobs)
    answers = [svc.request("GET", "/"), svc.request("GET", f"/jobs/{JOB}"), svc.request("GET", "/nope"),
               svc.request("GET", "/", host="evil:1"), svc.request("PUT", "/"), svc.request("HEAD", "/"),
               svc.post(reason="")]
    for status, headers, _ in answers:
        for k, v in rc.HEADERS.items():
            assert headers.get(k) == v, (status, k)
    assert [a[0] for a in answers] == [200, 200, 404, 421, 405, 405, 400]


def test_only_the_states_listed_are_shown_with_their_actions(svc):
    make_job(svc.jobs, state=rj.AWAITING_APPROVAL)
    make_job(svc.jobs, "j20261109_120001_beef", state=rj.APPLIED)
    _, _, index = svc.request("GET", "/")
    assert JOB in index and "beef" not in index
    _, _, applied = svc.request("GET", "/jobs/j20261109_120001_beef")
    assert "<form" not in applied and "No action" in applied


# --- the real CLI behind the service: its gates hold through it (F3.5, F4) ---

@pytest.fixture
def live(tmp_path):
    from test_router import Env
    env = Env(tmp_path)
    env.code(job_id=JOB)                                  # a real drafted job, AWAITING_APPROVAL
    s = Service(env.jobs, tmp_path / "audit.jsonl", rc.cli)
    s.env = env
    yield s
    s.stop()


def draft_path(jobs):
    return rj._last_draft(rj.open_job(JOB, jobs))[1]


def test_a_reject_through_the_cli_logs_via_ui_and_the_sha(live):
    status, _, text = live.post(reason="-x")             # a reason that looks like an option stays a reason
    assert status == 200, text
    job = rj.open_job(JOB, live.jobs)
    assert job.data["state"] == rj.REJECTED
    entry = job.data["log"][-1]
    assert (entry["new"], entry["reason"], entry["via"], entry["sha"]) == (rj.REJECTED, "-x", "ui",
                                                                           live.env.sha(JOB))


def test_a_draft_changed_since_the_page_is_refused_by_the_cli(live):
    token, sha = live.form()
    p = draft_path(live.jobs)
    p.write_text(json.dumps({**json.loads(p.read_text()), "for_human": "redrafted"}))
    before = (live.jobs / JOB / "job.json").read_bytes()
    status, _, text = live.post(token=token, sha=sha)
    assert status == 409 and "draft changed" in text
    assert (live.jobs / JOB / "job.json").read_bytes() == before


def test_a_state_the_cli_does_not_allow_is_refused_by_it(live):
    token, sha = live.form()
    job = rj.open_job(JOB, live.jobs)
    job.data["state"] = rj.APPLIED
    job.save()
    status, _, text = live.post(token=token, sha=sha)
    assert status == 409 and "only a research handoff" in text and "refused: refused" not in text
    assert rj.open_job(JOB, live.jobs).data["state"] == rj.APPLIED


def test_a_locked_job_is_refused_by_the_cli(live):
    token, sha = live.form()
    with rj.open_job(JOB, live.jobs).lock():
        status, _, text = live.post(token=token, sha=sha)
    assert status == 409 and "in use" in text
    assert rj.open_job(JOB, live.jobs).data["state"] == rj.AWAITING_APPROVAL


# --- router/job.py F4 ---

class Deps:
    clock = staticmethod(lambda: "2026-11-09T12:00:00Z")


def test_reject_and_abandon_check_the_sha_seen_and_record_via(tmp_path):
    make_job(tmp_path)
    with pytest.raises(rj.Refused, match="draft changed"):
        rj.reject(JOB, "x", deps=Deps, jobs_dir=tmp_path, sha="0" * 12)
    for bad in ("abc", sha12(tmp_path) + "\n", sha12(tmp_path).upper()):
        with pytest.raises(rj.Refused, match="not a draft sha"):
            rj.reject(JOB, "x", deps=Deps, jobs_dir=tmp_path, sha=bad)
    with pytest.raises(rj.Refused, match="via"):
        rj.abandon(JOB, "x", deps=Deps, jobs_dir=tmp_path, via="chat")
    assert rj.open_job(JOB, tmp_path).data["state"] == rj.AWAITING_APPROVAL
    job = rj.abandon(JOB, "x", deps=Deps, jobs_dir=tmp_path, sha=sha12(tmp_path), via="ui")
    assert job.data["log"][-1]["via"] == "ui" and job.data["log"][-1]["sha"] == sha12(tmp_path)


def test_a_sha_for_a_job_without_a_draft_is_refused_and_no_sha_changes_nothing(tmp_path):
    make_job(tmp_path, state=rj.DRAFT_FAILED, draft=None)
    with pytest.raises(rj.Refused, match="no draft"):
        rj.reject(JOB, "x", deps=Deps, jobs_dir=tmp_path, sha="a" * 12)
    job = rj.reject(JOB, "x", deps=Deps, jobs_dir=tmp_path)
    assert "via" not in job.data["log"][-1] and "sha" not in job.data["log"][-1]
