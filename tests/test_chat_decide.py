"""C4a (SPEC_CHAT_APP 13, 13.7): reject and abandon of a job through the chat's prepare and confirm, the decisions routes, the Decide
deep link, and the port matrix. The CLI is a recorder, except in the live tests that run the real `argus reject|abandon`."""
import http.client
import json
import os
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_chat_actions as t  # noqa: E402
import test_control as tc  # noqa: E402
from router import chat as rc  # noqa: E402
from router import chat_actions as ca  # noqa: E402
from router import job as rj  # noqa: E402

JOB = "j20261109_120000_abcd"
ISSUE = "j20261115_221000_beef"


@pytest.fixture
def svc(tmp_path):
    s = t.Service(tmp_path, cfg=t.CFG)
    yield s
    s.stop()


def mk(svc, **kw):
    return tc.make_job(svc.jobs, **kw)


def sha(svc, job=JOB):
    try:
        return tc.sha12(svc.jobs, job)
    except OSError:
        return ""


def reject(svc, **kw):
    body = {"action": "job_reject", "job": JOB, "sha": sha(svc), "reason": "tidak sesuai"}
    body.update(kw)
    return svc.prepare(**body)


def abandon(svc, **kw):
    body = {"action": "job_abandon", "job": JOB, "sha": sha(svc), "reason": ""}
    body.update(kw)
    return svc.prepare(**body)


# ---- the card, and the gates control had ---------------------------------------------------------------------------------------

def test_a_reject_card_names_the_job_the_draft_the_cost_and_the_reason_and_runs_nothing(svc):
    mk(svc)
    s, d = reject(svc)
    assert s == 200 and svc.runs == [] and d["exposure_usd"] == 0.0
    c = d["card"]
    assert c["title"] == "Reject the draft" and c["job"] == JOB and c["state"] == "AWAITING_APPROVAL" and c["kind"] == "code"
    assert c["sha12"] == sha(svc) and c["reason"] == "tidak sesuai" and c["cap_usd"] == 1.0 and c["spent_usd"] == 0.0


def test_confirm_runs_the_cli_with_the_sha_of_the_rebuilt_card_never_the_clients(svc):
    mk(svc)
    s, d = svc.confirm(reject(svc)[1]["token"])
    assert s == 200 and d == {"job": JOB, "done": True}
    assert svc.runs == [("reject", JOB, "tidak sesuai")] and svc.shas == [sha(svc)]


def test_a_confirm_carries_the_token_only_so_a_sha_sent_with_it_is_refused(svc):
    mk(svc)
    token = reject(svc)[1]["token"]
    svc.clock.t += 2
    assert svc.request("POST", "/api/confirm", {"token": token, "sha": "0" * 12})[0] == 400 and svc.runs == []


def test_an_abandon_without_a_reason_uses_the_default_one(svc):
    mk(svc, state=rj.DRAFTING, draft=None)
    s, d = abandon(svc, sha="")
    assert s == 200
    svc.confirm(d["token"])
    assert svc.runs == [("abandon", JOB, ca.ABANDON_DEFAULT)] and svc.shas == [""]


def test_a_reject_needs_a_reason(svc):
    mk(svc)
    s, d = reject(svc, reason="")
    assert s == 400 and "token" not in d


@pytest.mark.parametrize("reason", ["x" * 301, "dua\nbaris", "bidi‮", "nol​lebar", "tab\there", "sep "])
def test_a_reason_that_breaks_the_rules_is_refused_at_prepare(svc, reason):
    mk(svc)
    assert reject(svc, reason=reason)[0] == 400 and svc.runs == []


def test_a_reason_of_exactly_the_limit_and_one_starting_with_a_dash_are_kept(svc):
    mk(svc)
    assert reject(svc, reason="x" * 300)[0] == 200
    s, d = reject(svc, reason="-x --yes")
    svc.confirm(d["token"])
    assert svc.runs[-1] == ("reject", JOB, "-x --yes")


def test_the_sha_must_be_given_and_be_twelve_hex_characters(svc):
    mk(svc)
    for bad in ("abc", sha(svc).upper(), sha(svc) + "\n", sha(svc)[:11], 12):
        assert svc.prepare(action="job_reject", job=JOB, sha=bad, reason="x")[0] == 400
    assert svc.prepare(action="job_reject", job=JOB, reason="x")[0] == 400                   # missing: refused, not "no draft"


def test_the_sha_of_a_draft_that_is_not_the_one_shown_is_refused(svc):
    mk(svc)
    assert reject(svc, sha="0" * 12)[0] == 409
    assert abandon(svc, sha="")[0] == 409                                                    # "" against a job that has a draft is different


def test_a_draft_that_changes_between_prepare_and_confirm_is_refused_without_the_cli(svc):
    mk(svc)
    token = reject(svc)[1]["token"]
    p = svc.jobs / JOB / "runs" / f"{JOB}-d1" / "draft.json"
    p.write_text(json.dumps({**json.loads(p.read_text()), "for_human": "redrafted"}))
    assert svc.confirm(token)[0] == 409 and svc.runs == []


def test_a_draft_that_appears_between_prepare_and_confirm_is_refused(svc):
    mk(svc, state=rj.DRAFTING, draft=None)
    token = abandon(svc, sha="")[1]["token"]
    d = svc.jobs / JOB
    (d / "runs" / f"{JOB}-d1").mkdir(parents=True, exist_ok=True)
    (d / "runs" / f"{JOB}-d1" / "draft.json").write_text(json.dumps(tc.DRAFT))
    data = json.loads((d / "job.json").read_text())
    data["stages"]["d1"] = {"kind": "draft", "status": "DRAFTED", "run_id": f"{JOB}-d1"}
    (d / "job.json").write_text(json.dumps(data))
    assert svc.confirm(token)[0] == 409 and svc.runs == []


def test_a_state_that_changes_between_prepare_and_confirm_is_refused(svc):
    mk(svc)
    token = reject(svc)[1]["token"]
    p = svc.jobs / JOB / "job.json"
    data = json.loads(p.read_text())
    data["state"] = rj.APPLIED
    p.write_text(json.dumps(data))
    assert svc.confirm(token)[0] == 409 and svc.runs == []


@pytest.mark.parametrize("break_it", ["keyerror", "typeerror", "oserror", "badjson"])
def test_a_draft_that_cannot_be_read_is_a_refusal_at_prepare_and_never_no_draft(svc, break_it):
    d = mk(svc)
    data = json.loads((d / "job.json").read_text())
    if break_it == "keyerror":
        data["stages"]["d1"] = {"kind": "draft", "status": "DRAFTED"}                        # no run_id
    elif break_it == "typeerror":
        data["stages"] = []
    elif break_it == "oserror":
        (d / "runs" / f"{JOB}-d1" / "draft.json").unlink()
    else:
        (d / "runs" / f"{JOB}-d1" / "draft.json").write_text("{not json")
    (d / "job.json").write_text(json.dumps(data))
    s, body = svc.prepare(action="job_abandon", job=JOB, sha="", reason="")
    assert s in (409, 404) and "token" not in (body or {}) and svc.runs == []


def test_an_unreadable_draft_at_confirm_is_a_refusal(svc):
    d = mk(svc)
    token = reject(svc)[1]["token"]
    (d / "runs" / f"{JOB}-d1" / "draft.json").write_text("{not json")
    assert svc.confirm(token)[0] == 409 and svc.runs == []


@pytest.mark.parametrize("state", [rj.AWAITING_APPROVAL, rj.DRAFT_FAILED, rj.REVIEW_READY, rj.REVIEW_INVALID, rj.AWAITING_RESEARCH_REVIEW])
def test_a_reject_is_offered_in_the_rejectable_states(svc, state):
    mk(svc, state=state)
    assert reject(svc)[0] == 200


@pytest.mark.parametrize("state", [rj.DRAFTING, rj.REJECTED, rj.APPLIED, rj.ABANDONED, rj.BLOCKED])
def test_a_reject_in_any_other_state_is_refused(svc, state):
    mk(svc, state=state)
    s, d = reject(svc)
    assert s == 409 and "token" not in d


@pytest.mark.parametrize("state", sorted(ca.NOT_ABANDONABLE))
def test_an_abandon_in_a_state_control_did_not_allow_is_refused(svc, state):
    mk(svc, state=state)
    assert abandon(svc)[0] == 409


def test_an_abandon_is_offered_in_a_state_control_allowed(svc):
    mk(svc, state=rj.AWAITING_APPROVAL)
    assert abandon(svc)[0] == 200


def test_an_issue_job_is_decided_on_the_issue_page_not_here(svc):
    t.make_issue(svc.jobs, ISSUE)
    for fn in (reject, abandon):
        s, d = fn(svc, job=ISSUE, sha="")
        assert s == 409 and "token" not in d


def test_a_busy_job_gets_no_card(svc):
    mk(svc)
    svc.spawner.busy_ids.add(JOB)
    assert reject(svc)[0] == 409


def test_a_job_that_does_not_exist_or_is_not_a_ui_id_is_404(svc):
    mk(svc)
    for job in ("j20261109_120000_ffff", "jfoo", "..", "j20261109_120000_ABCD", JOB + "\n"):
        assert reject(svc, job=job)[0] == 404


def test_an_approve_is_not_an_action_at_all(svc):
    mk(svc)
    for action in ("job_approve", "approve", "job_redraft", "job_start"):
        assert svc.prepare(action=action, job=JOB, sha=sha(svc))[0] == 404


def test_extra_fields_are_refused(svc):
    mk(svc)
    assert reject(svc, repo="argus-viewer")[0] == 400 and reject(svc, message="x")[0] == 400


def test_a_symlinked_job_directory_is_not_read(svc, tmp_path):
    elsewhere = tmp_path / "elsewhere"
    tc.make_job(tmp_path, JOB)                         # a real job outside the jobs directory
    os.rename(tmp_path / JOB, elsewhere)
    os.symlink(elsewhere, svc.jobs / JOB)
    assert svc.prepare(action="job_abandon", job=JOB, sha="x" * 0 or "", reason="")[0] in (404, 409)
    assert svc.request("GET", "/api/decisions")[1]["decisions"] == []


def test_a_decision_never_reads_the_config_or_the_exposure(tmp_path, monkeypatch):
    s = t.Service(tmp_path, cfg=t.CFG)
    try:
        tc.make_job(s.jobs)

        def boom(*a, **k):
            raise AssertionError("the config or the exposure was touched")
        monkeypatch.setattr(ca.Actions, "exposure", boom)
        original = ca.Actions.cfg
        ca.Actions.cfg = property(boom)
        try:
            token = s.prepare(action="job_reject", job=JOB, sha=tc.sha12(s.jobs), reason="x")[1]["token"]
            assert s.confirm(token)[0] == 200
        finally:
            ca.Actions.cfg = original
    finally:
        s.stop()


def test_a_broken_config_still_allows_a_reject_and_the_issue_page_lists_no_repository(tmp_path):
    def broken():
        raise OSError("no config")
    s = t.Service(tmp_path, cfg=broken)
    try:
        tc.make_job(s.jobs)
        token = s.prepare(action="job_reject", job=JOB, sha=tc.sha12(s.jobs), reason="x")[1]["token"]
        assert s.confirm(token)[0] == 200
        assert s.request("GET", "/api/issues")[1]["repos"] == []
        assert s.prepare(action="issue_new", repo="argus-viewer", message="tulis sesuatu yang cukup panjang")[0] == 503
    finally:
        s.stop()


def test_one_unreadable_job_directory_does_not_stop_a_reject(svc):
    mk(svc)
    (svc.jobs / "j20261109_120001_beef").mkdir()
    (svc.jobs / "j20261109_120001_beef" / "job.json").write_text("{broken")
    token = reject(svc)[1]["token"]
    assert svc.confirm(token)[0] == 200


def test_the_cap_is_not_touched_by_a_decision_even_at_the_limit(svc):
    t.make_issue(svc.jobs, ISSUE, max_usd=5.0)         # more than the cap in use
    mk(svc)
    assert reject(svc)[0] == 200


# ---- the audit (F5) -------------------------------------------------------------------------------------------------------------

def test_the_attempt_is_written_before_the_cli_runs_and_carries_the_sha_and_the_exit(svc):
    mk(svc)
    seen = []

    def run(action, job_id, reason, sha=None):
        seen.append([r.get("attempt") or r.get("ok") for r in svc.audit()])
        svc.runs.append((action, job_id, reason))
        return 0, "ok"
    svc.actions.run = run
    svc.confirm(reject(svc)[1]["token"])
    assert seen == [["prepare", "confirm"]]
    rec = svc.audit()
    assert rec[-1]["ok"] == "confirm" and rec[-1]["sha"] == sha(svc) and rec[-1]["exit"] == 0 and rec[-1]["action"] == "job_reject"
    assert "tidak sesuai" not in svc.actions.audit_path.read_text()


def test_a_refusal_of_the_cli_is_shown_and_audited_with_its_exit_code(tmp_path):
    s = t.Service(tmp_path, cfg=t.CFG, run=lambda *a: (2, "refused: job j is in use by another command"))
    try:
        tc.make_job(s.jobs)
        token = s.prepare(action="job_reject", job=JOB, sha=tc.sha12(s.jobs), reason="x")[1]["token"]
        st, d = s.confirm(token)
        assert st == 409 and "in use" in d["refused"] and "refused:" not in d["refused"]
        assert s.audit()[-1]["refused"] == "cli" and s.audit()[-1]["exit"] == 2
    finally:
        s.stop()


def test_an_audit_that_cannot_be_written_means_no_cli_run(svc):
    mk(svc)
    token = reject(svc)[1]["token"]
    svc.actions.audit_path.unlink()
    svc.actions.audit_path.mkdir()
    assert svc.confirm(token)[0] == 503 and svc.runs == []


# ---- reading: decisions -------------------------------------------------------------------------------------------------------

def test_the_decisions_list_has_the_jobs_that_wait_for_a_decision_of_any_kind_newest_first(svc):
    mk(svc, job_id="j20261109_120000_aaaa")
    mk(svc, job_id="j20261109_130000_bbbb", state=rj.DRAFT_FAILED, draft=None)
    mk(svc, job_id="j20261109_140000_cccc", state=rj.APPLIED)
    t.make_issue(svc.jobs, ISSUE, state=rj.AWAITING_APPROVAL)                           # an issue job is not listed even in a rejectable state name
    d = svc.request("GET", "/api/decisions")[1]
    assert [r["id"] for r in d["decisions"]] == ["j20261109_130000_bbbb", "j20261109_120000_aaaa"] and d["capped"] is False
    row = d["decisions"][1]
    assert row["sha12"] == tc.sha12(svc.jobs, "j20261109_120000_aaaa") and row["allowed"] == ["reject", "abandon"]
    assert d["decisions"][0]["sha12"] is None and d["decisions"][0]["allowed"] == ["reject", "abandon"]


def test_the_list_is_cut_at_fifty_rows_and_two_hundred_directories(svc):
    for i in range(55):
        mk(svc, job_id=f"j20261109_1{i:05d}_{i:04x}")
    d = svc.request("GET", "/api/decisions")[1]
    assert len(d["decisions"]) == 50 and d["capped"] is True


def test_a_row_with_an_unreadable_draft_says_so_and_offers_nothing(svc):
    d = mk(svc)
    (d / "runs" / f"{JOB}-d1" / "draft.json").write_text("{not json")
    row = svc.request("GET", "/api/decisions")[1]["decisions"][0]
    assert row["draft_problem"] and row["allowed"] == [] and row["sha12"] is None


def test_the_detail_for_the_decide_link_is_any_non_issue_job_and_names_an_issue_job_only(svc):
    mk(svc, state=rj.DRAFTING, draft=None)
    t.make_issue(svc.jobs, ISSUE)
    row = svc.request("GET", f"/api/decisions/{JOB}")[1]
    assert row["id"] == JOB and row["allowed"] == ["abandon"] and row["state"] == "DRAFTING"
    assert svc.request("GET", f"/api/decisions/{ISSUE}")[1] == {"id": ISSUE, "kind": "issue", "state": "AWAITING_HUMAN"}
    for path in ("/api/decisions/jfoo", "/api/decisions/..", "/api/decisions/j20261109_120000_ffff"):
        assert svc.request("GET", path)[0] == 404


def test_opening_a_job_never_prepares_anything(svc):
    mk(svc)
    before = len(svc.audit())
    svc.request("GET", f"/api/decisions/{JOB}")
    svc.request("GET", "/api/decisions")
    assert len(svc.audit()) == before and svc.actions.prepared == {}


# ---- routes -------------------------------------------------------------------------------------------------------------------

def test_the_decide_link_path_answers_the_shell_without_reading_the_disk(svc):
    s, body = raw_get(svc, f"/jobs/{JOB}")
    root_status, root_body = raw_get(svc, "/")
    assert s == 200 and body == root_body                                                 # no job directory exists here at all


@pytest.mark.parametrize("path", [f"/jobs/{JOB}/", f"/jobs/{JOB}?x=1", f"/jobs/{JOB.upper()}", f"/jobs/{JOB[:-1]}%64", "/jobs/", "/jobs",
                                  f"/jobs/{JOB}/reject", f"/jobs/..%2Fx", "/jobs/jfoo", f"/jobs/{JOB}%2F"])
def test_every_other_jobs_path_is_404(svc, path):
    assert raw_get(svc, path)[0] == 404


def test_the_old_control_form_path_is_not_a_post_route(svc):
    mk(svc)
    s, _ = svc.request("POST", f"/jobs/{JOB}/reject", raw=b"token=x&sha=y&reason=z", headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert s == 405 and svc.runs == []


def raw_get(svc, path, host=t.HOST):
    c = http.client.HTTPConnection("127.0.0.1", svc.port, timeout=10)
    c.putrequest("GET", path, skip_host=True, skip_accept_encoding=True)
    c.putheader("Host", host)
    c.endheaders()
    r = c.getresponse()
    body = r.read()
    c.close()
    return r.status, body


# ---- the port matrix (13.4, 13.7 items 6 and 7) --------------------------------------------------------------------------------

class Bound:
    """A chat with the public port it is known by (8711 or 8712) on a free port, so the real ports are never bound."""

    def __init__(self, tmp_path, public):
        self.public = public
        self.jobs = tmp_path / "jobs"
        self.jobs.mkdir(exist_ok=True)
        self.actions = ca.Actions(self.jobs, t.CFG, state=tmp_path / "state", clock=t.Clock(), spawner=t.FakeSpawner(tmp_path / "state"),
                                  run=lambda *a: (0, "ok"), environ={})
        self.chat = rc.Chat(self.jobs, clock=t.Clock(), actions=self.actions)
        self.srv = rc.server(self.chat, port=0, public=public)
        self.port = self.srv.server_address[1]
        threading.Thread(target=lambda: self.srv.serve_forever(poll_interval=0.01), daemon=True).start()

    def get(self, path, host, extra=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        c.putrequest("GET", path, skip_host=True, skip_accept_encoding=True)
        c.putheader("Host", host)
        for k, v in (extra or {}).items():
            c.putheader(k, v)
        c.endheaders()
        r = c.getresponse()
        out = (r.status, dict((k.lower(), v) for k, v in r.getheaders()), r.read())
        c.close()
        return out

    def post(self, path, body, origin, host, extra=None):
        data = json.dumps(body).encode()
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        c.putrequest("POST", path, skip_host=True, skip_accept_encoding=True)
        for k, v in {"Host": host, "Origin": origin, "Content-Type": "application/json", "Content-Length": str(len(data)), **(extra or {})}.items():
            c.putheader(k, v)
        c.endheaders()
        c.send(data)
        r = c.getresponse()
        out = (r.status, dict((k.lower(), v) for k, v in r.getheaders()), r.read())
        c.close()
        return out

    def stop(self):
        self.srv.shutdown()
        self.srv.server_close()


@pytest.fixture(params=[8711, 8712])
def bound(request, tmp_path):
    b = Bound(tmp_path, request.param)
    yield b
    b.stop()


def test_127_0_0_1_is_a_host_on_both_ports_and_localhost_only_on_8711(bound):
    p = bound.public
    assert bound.get("/api/status", f"127.0.0.1:{p}")[0] == 200
    assert (bound.get("/api/status", f"localhost:{p}")[0] == 200) is (p == 8711)
    assert bound.get("/api/status", f"localhost:{p}")[0] in (200, 421)


@pytest.mark.parametrize("host", ["127.0.0.1:8710", "localhost:8710", "127.0.0.1:8000", "127.0.0.1", "localhost", "evil.test:8711", "0.0.0.0:8711",
                                  "[::1]:8711", "127.0.0.1:8711.evil", ""])
def test_any_other_host_is_refused_on_both_ports(bound, host):
    other = {8711: "8712", 8712: "8711"}[bound.public]
    assert bound.get("/api/status", host)[0] == 421
    assert bound.get("/api/status", f"127.0.0.1:{other}")[0] == 421                      # the other port's own name is not this one's
    assert bound.get("/api/status", f"localhost:{other}")[0] == 421


def test_the_origin_of_the_page_is_accepted_on_each_host_and_nothing_else(bound):
    p = bound.public
    body = {"action": "job_reject", "job": JOB, "sha": "0" * 12, "reason": "x"}
    ok = [(f"http://127.0.0.1:{p}", f"127.0.0.1:{p}")] + ([(f"http://localhost:{p}", f"localhost:{p}")] if p == 8711 else [])
    for origin, host in ok:
        assert bound.post("/api/prepare", body, origin, host)[0] == 404                   # past the gates (the job does not exist)
    for origin in ("http://localhost:8710", "http://127.0.0.1:8710", "http://evil.test", "null", "http://localhost:8712" if p == 8711 else "http://localhost:8711",
                   f"http://127.0.0.1:{p}.evil", f"https://127.0.0.1:{p}"):
        assert bound.post("/api/prepare", body, origin, f"127.0.0.1:{p}")[0] == 403
    assert bound.post("/api/prepare", body, f"http://127.0.0.1:{p}", f"127.0.0.1:{p}", {"Origin": f"http://localhost:8710"})[0] in (400, 403)


def test_localhost_as_origin_with_the_other_hosts_name_is_refused(bound):
    p = bound.public
    body = {"action": "job_reject", "job": JOB, "sha": "0" * 12, "reason": "x"}
    assert bound.post("/api/prepare", body, f"http://localhost:{p}", f"127.0.0.1:{p}")[0] == (404 if p == 8711 else 403)


@pytest.mark.parametrize("site", ["same-site", "cross-site"])
def test_a_same_site_or_cross_site_fetch_is_refused_on_api_and_post_on_both_ports(bound, site):
    p = bound.public
    assert bound.get("/api/status", f"127.0.0.1:{p}", {"Sec-Fetch-Site": site})[0] == 403
    body = {"action": "job_reject", "job": JOB, "sha": "0" * 12, "reason": "x"}
    assert bound.post("/api/prepare", body, f"http://127.0.0.1:{p}", f"127.0.0.1:{p}", {"Sec-Fetch-Site": site})[0] == 403


def test_the_csp_names_the_script_of_each_host_the_port_answers_to(bound):
    p = bound.public
    csp = bound.get("/", f"127.0.0.1:{p}")[1]["content-security-policy"]
    assert csp == rc.csp(p)
    scripts = [x for x in csp.split("script-src ")[1].split(";")[0].split(" ")]
    assert scripts == ([f"http://127.0.0.1:{p}/static/app.js", f"http://localhost:{p}/static/app.js"] if p == 8711 else [f"http://127.0.0.1:{p}/static/app.js"])
    assert "unsafe" not in csp and "'self' http" not in csp.split("script-src")[1].split(";")[0]


def test_a_big_cookie_gets_no_action_and_no_set_cookie(bound):
    p = bound.public
    s, h, _ = bound.get("/api/status", f"127.0.0.1:{p}", {"Cookie": "a=" + "b" * 60000})
    assert "set-cookie" not in h and s in (200, 431)
    assert bound.get("/api/status", f"127.0.0.1:{p}")[0] == 200


def test_the_decide_link_shell_is_served_on_both_hosts_of_8711(tmp_path):
    b = Bound(tmp_path, 8711)
    try:
        for host in ("127.0.0.1:8711", "localhost:8711"):
            s, h, body = b.get(f"/jobs/{JOB}", host)
            assert s == 200 and h["content-type"].startswith("text/html") and b"/static/app.js" in body
            assert "x-frame-options" in h and h["x-frame-options"] == "DENY" and "frame-ancestors 'none'" in h["content-security-policy"]
    finally:
        b.stop()


def test_only_the_two_ports_are_possible():
    for port in (8710, 8713, 8000, 0, 80):
        with pytest.raises(ValueError):
            rc.names_for(port)
        with pytest.raises(ValueError):
            rc.server(object(), port=0, public=port)


def test_the_cli_takes_a_port_and_refuses_any_other():
    sys.path.insert(0, str(t.ROOT if hasattr(t, "ROOT") else Path(__file__).resolve().parent.parent / "scripts"))
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import argus
    for bad in ("8713", "8710", "80", "x"):
        with pytest.raises(SystemExit):
            argus.main(["chat", "serve", "--port", bad])


# ---- the real CLI behind the chat's execute (what control's live tests proved) -----------------------------------------------------

@pytest.fixture
def live(tmp_path):
    from test_router import Env
    env = Env(tmp_path)
    env.code(job_id=JOB)                                  # a real drafted job, AWAITING_APPROVAL (as control's live tests)
    s = Live(tmp_path)
    s.env = env
    yield s
    s.stop()


class Live(t.Service):
    def __init__(self, tmp):
        super().__init__(tmp, cfg=t.CFG)
        self.actions.run = lambda action, job_id, reason, sha="": ca.control_cli(action, job_id, reason, sha, self.jobs)


def test_a_reject_through_the_real_cli_logs_via_ui_and_the_sha_and_keeps_a_dashed_reason(live):
    token = live.prepare(action="job_reject", job=JOB, sha=live.env.sha(JOB), reason="-x")[1]["token"]
    s, d = live.confirm(token)
    assert s == 200, d
    job = rj.open_job(JOB, live.jobs)
    entry = job.data["log"][-1]
    assert job.data["state"] == rj.REJECTED and (entry["reason"], entry["via"], entry["sha"]) == ("-x", "ui", live.env.sha(JOB))


def test_the_real_cli_refuses_a_locked_job_and_the_chat_says_so(live):
    token = live.prepare(action="job_reject", job=JOB, sha=live.env.sha(JOB), reason="x")[1]["token"]
    with rj.open_job(JOB, live.jobs).lock():
        s, d = live.confirm(token)
    assert s == 409 and "in use" in d["refused"]
    assert rj.open_job(JOB, live.jobs).data["state"] == rj.AWAITING_APPROVAL


def test_the_real_cli_gets_the_sha_so_a_redraft_between_confirm_and_the_lock_is_refused_by_it(live, monkeypatch):
    token = live.prepare(action="job_reject", job=JOB, sha=live.env.sha(JOB), reason="x")[1]["token"]
    real = ca.control_cli
    p = live.jobs / JOB / "runs" / f"{JOB}-d1" / "draft.json"

    def run(action, job_id, reason, sha=""):
        p.write_text(json.dumps({**json.loads(p.read_text()), "for_human": "redrafted"}))      # after the chat's last check, before the CLI's
        return real(action, job_id, reason, sha, live.jobs)
    live.actions.run = run
    s, d = live.confirm(token)
    assert s == 409 and "draft changed" in d["refused"]
    assert rj.open_job(JOB, live.jobs).data["state"] == rj.AWAITING_APPROVAL


def test_an_abandon_through_the_real_cli(live):
    token = live.prepare(action="job_abandon", job=JOB, sha=live.env.sha(JOB), reason="")[1]["token"]
    assert live.confirm(token)[0] == 200
    job = rj.open_job(JOB, live.jobs)
    assert job.data["state"] == rj.ABANDONED and job.data["log"][-1]["reason"] == ca.ABANDON_DEFAULT and job.data["log"][-1]["via"] == "ui"


def test_the_same_job_decided_twice_the_second_is_refused(live):
    a = live.prepare(action="job_reject", job=JOB, sha=live.env.sha(JOB), reason="x")[1]["token"]
    b = live.prepare(action="job_abandon", job=JOB, sha=live.env.sha(JOB), reason="")[1]["token"]
    assert live.confirm(a)[0] == 200
    assert live.confirm(b)[0] == 409 and rj.open_job(JOB, live.jobs).data["state"] == rj.REJECTED
