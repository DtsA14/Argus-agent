"""C3 (SPEC_CHAT_APP 12 and 12.10): research mode of the chat. A real server on a free port; the CLI is a recorder. The config is the
repository's own config.yaml, so the card is what the real go-live screen would show."""
import copy
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_chat_actions as t  # noqa: E402
from router import chat_actions as ca  # noqa: E402
from router import job as rj  # noqa: E402
from router import research as rr  # noqa: E402
from runner import load_config  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BASE = load_config(ROOT / "config.yaml")
Q = "Apa perbedaan utama antara Python 3.13 dan 3.14 dalam hal kinerja interpreter?"
RID = "j20261115_222000_ab12"


def config(**over):
    c = copy.deepcopy(BASE)
    c["chat"] = {"daily_cap_usd": 2.0}
    for k, v in over.items():
        c[k] = v
    return c


@pytest.fixture
def svc(tmp_path):
    s = t.Service(tmp_path, cfg=config())
    yield s
    s.stop()


def prep(svc, **kw):
    return svc.prepare(action="research_new", message=Q, **kw)


def make_research(jobs, job_id=RID, state=rr.REPORT_READY, via="ui", max_usd=1.0, e1="CHECKED", report="# Laporan\n\nIsi.\n",
                  question=Q, created=t.NOW - 100, stages=True, kind="research"):
    d = jobs / job_id
    d.mkdir(parents=True)
    data = {"job": job_id, "kind": kind, "state": state, "max_usd": max_usd, "created_at": t.iso(created),
            "inputs": {"question": question}, "stages": {"e1": {"kind": "check", "run_id": f"{job_id}-e1", "status": e1,
                                                               "counts": {"SUPPORTED": 3, "PARTIAL": 1}}} if stages else {},
            "log": [{"at": t.iso(created), "what": "created", **({"via": via} if via else {})}]}
    (d / "job.json").write_text(json.dumps(data))
    if report is not None:
        (d / "REPORT.md").write_text(report)
    return d


# ---- the card: what the CLI's own go-live screen would show ---------------------------------------------------------------

def test_prepare_shows_the_whole_go_live_screen_and_runs_nothing(svc):
    s, d = prep(svc)
    assert s == 200 and svc.actions.spawner.calls == []
    c = d["card"]
    assert c["title"] == "Start a research job" and c["message"] == Q and c["job_cap_usd"] == 1.0 and d["exposure_usd"] == 1.0
    assert c["profile"] == "deepseek"
    for stage in rr.STAGE_KINDS:
        assert f"{stage} deepseek:deepseek-flash" in c["stage_models"]
    assert "planner $0.05" in c["stage_caps"] and "deepseek" in c["web"] and "do not put secrets" in c["data_sent"]


def test_the_card_facts_are_the_ones_of_the_cli_screen_function(svc):
    c = prep(svc)[1]["card"]
    cfg = config()
    assert c["facts"] == json.loads(json.dumps(rr.screen_facts(rj.stage_config(cfg, 1.0), rr.stage_roles(cfg, None))))


def test_confirm_starts_the_cli_with_the_code_key_and_the_question_in_a_file(svc):
    token = prep(svc)[1]["token"]
    s, d = svc.confirm(token)
    assert s == 200 and d["started"] is True and ca.UI_ID.fullmatch(d["job"])
    (call,) = svc.actions.spawner.calls
    a = call["argv"]
    assert call["action"] == "research" and call["job"] == d["job"] and Path(call["message"]).read_text() == Q
    assert a[a.index("research") + 1:a.index("research") + 3] == ["--question-file", str(call["message"])]
    assert a[a.index("--job-id") + 1] == d["job"] and a[a.index("--via") + 1] == "ui" and "--yes" in a
    assert a[a.index("--key" + "-file") + 1] == t.KEY                               # the code one, never the writer's
    assert "--max-usd" not in a and "--profile" not in a and Q not in a


def test_the_question_is_not_in_the_audit_and_the_audit_has_the_two_steps(svc):
    svc.confirm(prep(svc)[1]["token"])
    assert Q not in svc.actions.audit_path.read_text()
    rec = svc.audit()
    assert [r.get("ok") or r.get("attempt") for r in rec] == ["prepare", "confirm", "confirm"] and rec[-1]["action"] == "research_new"


@pytest.mark.parametrize("extra", [{"profile": "free"}, {"max_usd": "9"}, {"repo": "argus-viewer"}, {"job": RID}, {"reason": "x"}])
def test_a_research_job_takes_the_question_and_nothing_else(svc, extra):
    s, d = prep(svc, **extra)
    assert s == 400 and "token" not in (d or {})


@pytest.mark.parametrize("q", ["terlalu pendek", "x" * 2001, "", "   ", "pertanyaan‮terbalik tentang python versi tiga empat",
                               "pertanyaan dengan​karakter nol lebar tentang python", "pertanyaan\U000e0041tag tentang python 3.14",
                               "pertanyaan dengan variation️ selector python", "pertanyaan memuat sk-" + "a" * 30 + " kunci python",
                               "pertanyaan dengan api_key = \"abc\" di dalamnya python"])
def test_a_question_that_breaks_the_text_rules_is_refused_at_prepare(svc, q):
    s, d = svc.prepare(action="research_new", message=q)
    assert s == 400 and svc.actions.spawner.calls == [] and "token" not in (d or {})


def test_a_question_of_exactly_the_limits_is_accepted(svc):
    assert svc.prepare(action="research_new", message="p" * 20)[0] == 200
    assert svc.prepare(action="research_new", message="q" * 2000)[0] == 200
    assert svc.prepare(action="research_new", message="p" * 19)[0] == 400


def test_without_the_code_key_there_is_no_card(tmp_path):
    s = t.Service(tmp_path, cfg=config(), environ={ca.WRITER_KEY_ENV: t.WKEY})
    try:
        st, d = s.prepare(action="research_new", message=Q)
        assert st == 409 and "token" not in d
    finally:
        s.stop()


def test_the_writer_key_does_not_stand_in_for_the_code_key_and_the_code_key_alone_is_enough(tmp_path):
    s = t.Service(tmp_path, cfg=config(), environ={ca.KEY_ENV: t.KEY})
    try:
        assert s.prepare(action="research_new", message=Q)[0] == 200
    finally:
        s.stop()


@pytest.mark.parametrize("profile", ["free", "deepinfra"])
def test_a_profile_that_needs_more_than_the_one_deepseek_key_is_refused_before_a_token(tmp_path, profile):
    c = config()
    c["research_job"]["profile"] = profile
    s = t.Service(tmp_path, cfg=c)
    try:
        st, d = s.prepare(action="research_new", message=Q)
        assert st == 409 and "token" not in d and s.actions.spawner.calls == []
    finally:
        s.stop()


def test_a_cap_below_what_the_stages_need_is_refused(tmp_path):
    c = config()
    c["research_job"]["max_usd"] = 0.2
    s = t.Service(tmp_path, cfg=c)
    try:
        assert s.prepare(action="research_new", message=Q)[0] == 409
    finally:
        s.stop()


def test_the_card_cap_is_the_one_start_reads_when_max_usd_is_not_set(tmp_path):
    c = config()
    del c["research_job"]["max_usd"]
    s = t.Service(tmp_path, cfg=c)
    try:
        assert s.prepare(action="research_new", message=Q)[1]["card"]["job_cap_usd"] == 1.0
    finally:
        s.stop()


def test_a_config_without_a_research_job_has_no_research_card(tmp_path):
    c = config()
    del c["research_job"]
    s = t.Service(tmp_path, cfg=c)
    try:
        assert s.prepare(action="research_new", message=Q)[0] == 409
    finally:
        s.stop()


def test_a_stage_model_changed_between_prepare_and_confirm_is_refused(tmp_path):
    c = config()
    s = t.Service(tmp_path, cfg=c)
    try:
        token = prep(s)[1]["token"]
        c["roles"]["researcher"]["model"] = "deepseek:deepseek-v4-pro"
        st, d = s.confirm(token)
        assert st == 409 and s.actions.spawner.calls == []
    finally:
        s.stop()


def test_a_web_price_changed_between_prepare_and_confirm_is_refused(tmp_path):
    c = config()
    s = t.Service(tmp_path, cfg=c)
    try:
        token = prep(s)[1]["token"]
        c["web_research"]["price_usd_per_request"]["search"] = 0.5
        assert s.confirm(token)[0] == 409 and s.actions.spawner.calls == []
    finally:
        s.stop()


def test_a_token_works_once_for_research(svc):
    token = prep(svc)[1]["token"]
    assert svc.confirm(token)[0] == 200
    assert svc.confirm(token)[0] == 403 and len(svc.actions.spawner.calls) == 1


# ---- the daily cap (12.10 item 1) --------------------------------------------------------------------------------------------

def test_two_research_jobs_fit_in_two_dollars_and_the_third_is_refused(svc):
    for _ in range(2):
        assert svc.confirm(prep(svc)[1]["token"])[0] == 200
    s, d = prep(svc)
    assert s == 403 and "token" not in d


def test_the_cap_is_checked_again_at_confirm(svc):
    a, b, c = (prep(svc)[1]["token"] for _ in range(3))
    assert svc.confirm(a)[0] == 200 and svc.confirm(b)[0] == 200
    assert svc.confirm(c)[0] == 403 and len(svc.actions.spawner.calls) == 2


def test_research_jobs_in_the_directory_count_with_their_full_cap(svc):
    make_research(svc.jobs, RID, state="RESEARCHING", max_usd=1.0)
    assert svc.actions.exposure() == pytest.approx(1.0)
    make_research(svc.jobs, "j20261115_222100_ab13", max_usd=1.0)
    assert svc.actions.exposure() == pytest.approx(2.0) and prep(svc)[0] == 403


def test_a_research_job_started_from_the_terminal_with_via_counts_and_one_without_does_not(svc):
    make_research(svc.jobs, RID, via="ui")
    make_research(svc.jobs, "j20261115_222100_ab13", via=None)
    assert svc.actions.exposure() == pytest.approx(1.0)


def test_a_research_job_older_than_a_day_does_not_count(svc):
    make_research(svc.jobs, RID, created=t.NOW - 25 * 3600)
    assert svc.actions.exposure() == 0


def test_a_cap_raised_in_the_config_after_the_job_began_counts_the_larger(svc):
    make_research(svc.jobs, RID, max_usd=0.4)
    assert svc.actions.exposure() == pytest.approx(1.0)


@pytest.mark.parametrize("bad", [None, "x", [1]])
def test_a_research_job_whose_cap_cannot_be_read_is_an_unknown_exposure_not_zero(svc, bad):
    d = make_research(svc.jobs, RID)
    data = json.loads((d / "job.json").read_text())
    if bad is None:
        del data["max_usd"]
    else:
        data["max_usd"] = bad
    (d / "job.json").write_text(json.dumps(data))
    with pytest.raises(ca.Refusal) as e:
        svc.actions.exposure()
    assert e.value.status == 503


def test_a_confirm_counts_at_once_before_the_directory_shows_the_job(svc):
    assert svc.confirm(prep(svc)[1]["token"])[0] == 200
    assert svc.actions.exposure() == pytest.approx(1.0)


def test_a_job_the_directory_shows_is_not_counted_twice(svc):
    st, d = svc.confirm(prep(svc)[1]["token"])
    make_research(svc.jobs, d["job"], created=t.NOW)
    assert svc.actions.exposure() == pytest.approx(1.0)


def test_the_audit_is_a_net_when_the_cli_lost_the_via_field(svc):
    st, d = svc.confirm(prep(svc)[1]["token"])
    svc.actions.pending.clear()
    make_research(svc.jobs, d["job"], via=None, created=t.NOW)
    assert svc.actions.exposure() == pytest.approx(1.0)


def test_an_old_audit_line_is_not_counted(svc):
    svc.confirm(prep(svc)[1]["token"])
    svc.actions.pending.clear()
    svc.clock.t += 25 * 3600
    assert svc.actions.exposure() == 0


def test_an_audit_line_of_another_action_or_a_failed_confirm_is_not_counted(svc):
    svc.actions.audit(action="issue_new", ok="confirm", job="j20261115_221000_beef")
    svc.actions.audit(action="research_new", attempt="confirm", job="j20261115_221000_beef")
    svc.actions.audit(action="research_new", refused="cap", job="j20261115_221000_beef")
    assert svc.actions.exposure() == 0


def test_an_audit_that_cannot_be_read_is_an_unknown_exposure(svc):
    svc.confirm(prep(svc)[1]["token"])
    svc.actions.audit_path.unlink()
    svc.actions.audit_path.mkdir()
    with pytest.raises(ca.Refusal):
        svc.actions.exposure()


def test_issues_and_research_share_the_one_cap(svc):
    t.make_issue(svc.jobs, "j20261115_221000_beef", max_usd=0.5)
    assert svc.actions.exposure() == pytest.approx(0.5)
    make_research(svc.jobs, RID, max_usd=1.0)
    assert svc.actions.exposure() == pytest.approx(1.5)
    assert prep(svc)[0] == 403                            # 1.5 + 1.0 passes 2.0


# ---- reading --------------------------------------------------------------------------------------------------------------

def test_the_list_has_research_jobs_only_newest_first(svc):
    make_research(svc.jobs, "j20261115_220000_aaaa")
    make_research(svc.jobs, "j20261115_221000_bbbb", state="RESEARCHING")
    t.make_issue(svc.jobs, "j20261115_222000_cccc")
    st, d = svc.request("GET", "/api/research")
    assert st == 200 and [r["id"] for r in d["research"]] == ["j20261115_221000_bbbb", "j20261115_220000_aaaa"]
    assert d["research"][0]["title"].startswith("Apa perbedaan") and len(d["research"][0]["title"]) <= 80


def test_the_list_stops_at_fifty(svc):
    for i in range(55):
        make_research(svc.jobs, f"j20261115_2200{i:02d}_{i:04x}")
    assert len(svc.request("GET", "/api/research")[1]["research"]) == 50


def test_a_checked_report_shows_the_report_cost_banner_and_counts(svc):
    d = make_research(svc.jobs)
    run = d / "runs" / f"{RID}-e1"
    run.mkdir(parents=True)
    base = {"call_id": "c1", "model": "deepseek:deepseek-flash", "node": "check", "role": "researcher", "ts": 1.0}
    evs = [{"event": "llm_call_started", **base, "worst_usd_nano": 20_000_000, "worst_tokens": 100},
           {"event": "llm_call", **base, "status": "ok", "usd_nano": 12_000_000, "tokens": 10, "input_tokens": 5,
            "output_tokens": 5, "cache_read": None, "est_input": 5}]
    (run / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in evs))
    st, r = svc.request("GET", f"/api/research/{RID}")
    assert st == 200 and r["state"] == "REPORT_READY" and r["checked"] is True and r["counts"] == {"SUPPORTED": 3, "PARTIAL": 1}
    assert r["report"]["text"].startswith("# Laporan") and r["report"]["cut"] is False and r["spent_usd"] == pytest.approx(0.012)
    assert r["banner"] == ca.BANNER and r["cap_usd"] == 1.0 and r["stalled"] is False and r["question"] == Q


@pytest.mark.parametrize("state, e1", [("REPORT_READY", "NOT_CHECKED"), ("REPORT_READY", None), ("BLOCKED", "CHECKED"),
                                         ("ABANDONED", "CHECKED"), ("CHECKING", "CHECKED"), ("REPORT_READY", "checked")])
def test_only_a_report_ready_job_whose_e1_status_is_checked_is_labelled_checked(svc, state, e1):
    make_research(svc.jobs, state=state, e1=e1)
    assert svc.request("GET", f"/api/research/{RID}")[1]["checked"] is False


def test_a_report_that_says_checked_in_its_own_text_does_not_make_the_job_checked(svc):
    make_research(svc.jobs, state="BLOCKED", e1="NOT_CHECKED", report="# Laporan\n\nChecked by e1: every item has a verdict.\n")
    assert svc.request("GET", f"/api/research/{RID}")[1]["checked"] is False


@pytest.mark.parametrize("state", sorted(rr.RUNNING))
def test_a_running_job_with_no_run_of_this_service_is_stalled(svc, state):
    make_research(svc.jobs, state=state, report=None)
    r = svc.request("GET", f"/api/research/{RID}")[1]
    assert r["stalled"] is True and r["busy"] is False


def test_a_running_job_with_a_run_of_this_service_is_not_stalled(svc):
    make_research(svc.jobs, state="RESEARCHING", report=None)
    svc.actions.spawner.busy_ids.add(RID)
    r = svc.request("GET", f"/api/research/{RID}")[1]
    assert r["stalled"] is False and r["busy"] is True


def test_a_finished_job_is_never_stalled(svc):
    make_research(svc.jobs, state="REPORT_READY")
    assert svc.request("GET", f"/api/research/{RID}")[1]["stalled"] is False


def test_a_report_over_the_display_limit_is_cut_with_the_harness_marker(svc):
    make_research(svc.jobs, report="linea baris yang cukup panjang\n" * 10_000)             # about 320 KB
    r = svc.request("GET", f"/api/research/{RID}")[1]["report"]
    assert r["cut"] is True and "[dipotong harness" in r["text"] and len(r["text"].encode()) <= 256 * 1024


def test_a_report_over_a_mebibyte_is_withheld_but_the_job_is_still_shown(svc):
    make_research(svc.jobs, report="x" * (2 * 1024 * 1024))
    st, r = svc.request("GET", f"/api/research/{RID}")
    assert st == 200 and r["state"] == "REPORT_READY" and "text" not in r["report"] and "terminal" in r["report"]["withheld"]


def test_a_report_that_is_a_symlink_is_not_read(svc, tmp_path):
    d = make_research(svc.jobs, report=None)
    secret = tmp_path / "secret.md"
    secret.write_text("rahasia host")
    os.symlink(secret, d / "REPORT.md")
    st, r = svc.request("GET", f"/api/research/{RID}")
    assert st == 200 and "rahasia" not in json.dumps(r) and "withheld" in r["report"]


def test_a_report_with_a_second_name_is_not_read(svc, tmp_path):
    d = make_research(svc.jobs, report=None)
    other = tmp_path / "other.md"
    other.write_text("isi lain")
    os.link(other, d / "REPORT.md")
    assert "isi lain" not in json.dumps(svc.request("GET", f"/api/research/{RID}")[1])


def test_a_report_with_a_key_like_string_is_withheld_whole_and_says_where_to_read_it(svc):
    make_research(svc.jobs, report="# Laporan\n\nkunci: sk-" + "a" * 30 + "\n")
    r = svc.request("GET", f"/api/research/{RID}")[1]["report"]
    assert "text" not in r and f"argus status {RID}" in r["withheld"] and "sk-aaaa" not in json.dumps(r)


@pytest.mark.parametrize("hidden", ["‮", "​", "\U000e0041", "️", "\U000e0100", "᠎", "͏", "ㅤ", "ﾠ",
                                    "⁡", "￹", "", "͸"])
def test_hidden_characters_of_every_class_are_removed_from_the_report(svc, hidden):
    make_research(svc.jobs, report=f"aman{hidden}teks\n")
    assert svc.request("GET", f"/api/research/{RID}")[1]["report"]["text"] == "amanteks\n"


def test_a_question_and_a_report_keep_their_newlines_and_tabs(svc):
    make_research(svc.jobs, report="a\n\tb\n", question="baris satu\nbaris dua " + "x" * 30)
    r = svc.request("GET", f"/api/research/{RID}")[1]
    assert r["report"]["text"] == "a\n\tb\n" and r["question"].startswith("baris satu\nbaris dua")


def test_a_hostile_html_report_is_returned_as_plain_json_text(svc):
    make_research(svc.jobs, report="<script>alert(1)</script>\n[x](javascript:alert(1))\n")
    st, r = svc.request("GET", f"/api/research/{RID}")
    assert st == 200 and r["report"]["text"].startswith("<script>")               # text; the page puts it in with textContent


def test_a_symlinked_runs_directory_is_not_followed_for_the_cost(svc, tmp_path):
    d = make_research(svc.jobs)
    elsewhere = tmp_path / "elsewhere"
    (elsewhere / f"{RID}-e1").mkdir(parents=True)
    (elsewhere / f"{RID}-e1" / "events.jsonl").write_text("")
    os.symlink(elsewhere, d / "runs")
    assert svc.request("GET", f"/api/research/{RID}")[1]["spent_usd"] is None      # unknown, never 0


def test_a_symlinked_ledger_is_not_followed_for_the_cost(svc, tmp_path):
    d = make_research(svc.jobs)
    (d / "runs" / f"{RID}-e1").mkdir(parents=True)
    target = tmp_path / "x.jsonl"
    target.write_text("")
    os.symlink(target, d / "runs" / f"{RID}-e1" / "events.jsonl")
    assert svc.request("GET", f"/api/research/{RID}")[1]["spent_usd"] is None


def test_an_issue_job_and_a_bad_id_are_404_on_the_research_route(svc):
    t.make_issue(svc.jobs, "j20261115_221000_beef")
    for path in ("/api/research/j20261115_221000_beef", "/api/research/jfoo", "/api/research/..", "/api/research/j20261115_000000_0000"):
        assert svc.request("GET", path)[0] == 404


def test_a_research_job_is_404_on_the_issue_route(svc):
    make_research(svc.jobs)
    assert svc.request("GET", f"/api/issues/{RID}")[0] == 404 and svc.request("GET", "/api/issues")[1]["issues"] == []


def test_before_the_job_exists_the_page_can_see_starting_or_the_cli_refusal(svc):
    new = "j20261115_223000_dd01"
    svc.actions.spawner.busy_ids.add(new)
    assert svc.request("GET", f"/api/research/{new}")[1]["state"] == "starting"
    svc.actions.spawner.busy_ids.clear()
    svc.actions.spawner.outcome = lambda job_id: {"code": 2, "line": "the job cap must be at least $0.80", "action": "research", "text": None}
    r = svc.request("GET", f"/api/research/{new}")[1]
    assert r["state"] == "refused" and "at least" in r["line"]


def test_the_research_routes_answer_get_only_and_the_gates_still_apply(svc):
    assert svc.request("POST", "/api/research", {"x": 1})[0] == 405
    assert svc.request("GET", "/api/research", host="evil.test:8712")[0] == 421


@pytest.mark.parametrize("only, on", [("research_job", True), ("issue_writer", True), ("chat", False)])
def test_the_service_has_actions_when_the_config_has_a_research_job_or_an_issue_writer(tmp_path, monkeypatch, only, on):
    from router import chat as rc
    got = {}

    class Stop(Exception):
        pass

    def fake_server(chat, port=rc.PORT):
        got["actions"] = chat.actions
        raise Stop

    monkeypatch.setattr(rc, "server", fake_server)
    monkeypatch.setattr(ca, "STATE", tmp_path / "state")
    cfg = {only: copy.deepcopy(BASE.get(only) or {"x": 1})}
    with pytest.raises(Stop):
        rc.serve(tmp_path, cfg)
    assert (got["actions"] is not None) is on
