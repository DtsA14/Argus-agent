"""P1 of the chat manager (SPEC_CHAT_MANAGER_P1 rev 1, 5, 10): the session card (`manager_new`), the turn route, the read route, the exposure and the kind in the page's reads.
A real server on a free port; the CLI is a recorder; the config is the repository's own."""
import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_chat_actions as t  # noqa: E402
from router import chat_actions as ca  # noqa: E402
from router import job as rj  # noqa: E402
from router import manager_job as mj  # noqa: E402
from router import stage_data as sd  # noqa: E402
from runner import load_config  # noqa: E402

BASE = load_config(Path(__file__).resolve().parent.parent / "config.yaml")
JOB = "j20261115_220000_abcd"
JOB2 = "j20261115_220100_abce"
TURN = "/api/manager/turn"


def config(daily=2.0):
    c = copy.deepcopy(BASE)
    c["chat"]["daily_cap_usd"] = daily
    return c


@pytest.fixture
def svc(tmp_path):
    s = t.Service(tmp_path, cfg=config())
    yield s
    s.stop()


def make_session(jobs, job_id=JOB, state="OPEN", via="ui", created=t.NOW - 100, max_usd=0.20, conversation=None, kind="manager", spent_nano=0, extra_log=()):
    d = jobs / job_id
    d.mkdir(parents=True)
    log = [{"at": t.iso(created), "what": "created", **({"via": via} if via else {})}, *extra_log]
    (d / "job.json").write_text(json.dumps({"job": job_id, "kind": kind, "state": state, "max_usd": max_usd, "created_at": t.iso(created),
                                            "inputs": {"role": "manager", "model": "openrouter:deepseek/deepseek-v4.1-flash-1017", "readable_repos": []},
                                            "conversation": conversation or [], "stages": {"m1": {"kind": "manager", "run_id": f"{job_id}-m1", "cap_usd": max_usd, "started_at": t.iso(created)}},
                                            "log": log}))
    r = d / "runs" / f"{job_id}-m1"
    r.mkdir(parents=True)
    if spent_nano:
        (r / "events.jsonl").write_text(json.dumps({"event": "llm_call_started", "call_id": "c1", "model": "m", "node": "manager", "role": "manager", "ts": 1, "worst_usd_nano": spent_nano, "worst_tokens": 1}) + "\n")
    return d


def turn(svc, session=JOB, message="Halo", **kw):
    return svc.request("POST", TURN, {"session": session, "message": message}, **kw)


# ---- the session card ----------------------------------------------------------------------------------------------------

def test_prepare_shows_the_numbers_of_the_config_and_runs_nothing(svc):
    status, out = svc.prepare(action="manager_new")
    assert status == 200 and svc.spawner.calls == []
    c, m = out["card"], mj.settings(svc.actions.cfg)
    assert c["action"] == "manager_new" and c["model"] == BASE["roles"]["manager"]["model"] and c["job_cap_usd"] == m["session_cap_usd"] == 0.20
    assert c["turn_cap_usd"] == 0.03 and c["ttl_hours"] == 12 and c["max_turns"] == 200 and "three calls" in c["turn_note"] and "summar" in c["turn_note"]
    assert "no repository content" in c["data_sent"] and "cannot approve" in c["confirms"]
    assert out["exposure_usd"] == 0.20


def test_a_session_takes_no_fields_and_needs_a_key_and_a_config(tmp_path):
    for env, cfg, body, status in (({ca.WRITER_KEY_ENV: t.WKEY, ca.KEY_ENV: t.KEY}, config(), {"message": "x"}, 400), ({}, config(), {}, 409)):
        (tmp_path / str(status)).mkdir()
        s = t.Service(tmp_path / str(status), cfg=cfg, environ=env)
        try:
            assert s.prepare(action="manager_new", **body)[0] == status
        finally:
            s.stop()
    bad = config()
    del bad["chat"]["manager"]
    (tmp_path / "x").mkdir()
    s = t.Service(tmp_path / "x", cfg=bad)
    try:
        assert s.prepare(action="manager_new")[0] == 409
    finally:
        s.stop()


def test_confirm_starts_exactly_one_new_without_a_key_and_the_exposure_counts(svc):
    out = svc.prepare(action="manager_new")[1]
    status, body = svc.confirm(out["token"])
    assert status == 200 and body["started"] and len(svc.spawner.calls) == 1
    c = svc.spawner.calls[0]
    py, script = c["argv"][0], c["argv"][1]
    assert c["argv"][2:] == ["--jobs-dir", str(svc.jobs), "manager", "new", "--job-id", body["job"], "--via", "ui", "--yes"] and c["message"] is None
    assert "--key-file" not in c["argv"] and c["action"] == "manager"
    assert svc.actions.exposure() == pytest.approx(0.20)                      # pending until the job file exists
    assert [a for a in svc.audit() if a.get("action") == "manager_new"][-1]["ok"] == "confirm"


def test_two_sessions_in_a_row_cross_a_small_daily_cap(tmp_path):
    s = t.Service(tmp_path, cfg=config(daily=0.30))
    try:
        assert s.confirm(s.prepare(action="manager_new")[1]["token"])[0] == 200
        status, out = s.prepare(action="manager_new")
        assert status == 403 and "daily" in json.dumps(out).lower()
    finally:
        s.stop()


def test_exposure_counts_a_session_started_via_the_ui_for_a_day_and_nothing_else(svc):
    make_session(svc.jobs, JOB)
    assert svc.actions.exposure() == pytest.approx(0.20)
    make_session(svc.jobs, JOB2, via=None)
    assert svc.actions.exposure() == pytest.approx(0.20)                      # not via ui: not counted
    svc.clock.t += 25 * 3600
    assert svc.actions.exposure() == 0.0


def test_a_session_with_a_bad_budget_makes_the_exposure_unknown_never_zero(svc):
    make_session(svc.jobs, JOB, max_usd=float("nan"))
    with pytest.raises(ca.Refusal) as e:
        svc.actions.exposure()
    assert e.value.status == 503


def test_a_big_session_never_makes_the_exposure_unknown(svc):
    conv = [{"from": "human", "at": t.iso(t.NOW), "text": "x" * 2000}, {"from": "manager", "at": t.iso(t.NOW), "say": "y" * 2000, "propose": None, "usd": 0.0, "calls": 1}] * 40
    d = make_session(svc.jobs, JOB, conversation=conv)
    assert (d / "job.json").stat().st_size < ca.JOB_JSON_MAX
    assert svc.actions.exposure() == pytest.approx(0.20)


def test_the_audit_net_counts_a_confirmed_session_whose_via_was_lost(svc):
    make_session(svc.jobs, JOB, via=None)
    svc.actions.audit(action="manager_new", ok="confirm", job=JOB)
    assert svc.actions.exposure() == pytest.approx(0.20)


def test_execute_of_an_unknown_action_is_an_error_and_never_a_new_job(svc):
    with pytest.raises(ca.Refusal) as e:
        svc.actions.execute("manager_turn", {}, {})
    assert e.value.status == 500 and svc.spawner.calls == []


# ---- the turn route -------------------------------------------------------------------------------------------------------

def test_a_turn_spawns_the_one_argv_after_one_audit_line_without_the_text(svc, monkeypatch):
    make_session(svc.jobs)
    n = {}
    real = svc.spawner.spawn

    def spy(*a, **k):
        n["audit_before"] = len(svc.audit())
        return real(*a, **k)
    monkeypatch.setattr(svc.spawner, "spawn", spy)
    status, out = turn(svc, message="rahasia: pesan saya")
    assert status == 200 and out == {"job": JOB, "started": True}
    c = svc.spawner.calls[0]
    msgfile = Path(c["argv"][c["argv"].index("--message-file") + 1])
    assert c["argv"][2:] == ["--jobs-dir", str(svc.jobs), "manager", "turn", JOB, "--message-file", str(msgfile), "--via", "ui", "--key-file", t.WKEY, "--yes"]
    assert msgfile.read_text() == "rahasia: pesan saya" and "pesan saya" not in " ".join(c["argv"][:-1]).replace(str(msgfile), "")
    lines = svc.audit()
    assert n["audit_before"] == 1 and lines[0]["attempt"] == "manager_turn" and lines[0]["job"] == JOB
    assert not any("rahasia" in json.dumps(x) for x in lines)


def test_the_manager_key_slot_comes_first_then_the_writer_then_the_code_key(tmp_path):
    for env, want in (({ca.MANAGER_KEY_ENV: "/k/m", ca.WRITER_KEY_ENV: "/k/w", ca.KEY_ENV: "/k/c"}, "/k/m"), ({ca.WRITER_KEY_ENV: "/k/w", ca.KEY_ENV: "/k/c"}, "/k/w"), ({ca.KEY_ENV: "/k/c"}, "/k/c")):
        (tmp_path / want.replace("/", "_")).mkdir()
        s = t.Service(tmp_path / want.replace("/", "_"), cfg=config(), environ=env)
        try:
            make_session(s.jobs)
            assert turn(s)[0] == 200 and s.spawner.calls[0]["argv"][s.spawner.calls[0]["argv"].index("--key-file") + 1] == want
        finally:
            s.stop()


@pytest.mark.parametrize("what, make, status", [
    ("not via ui", dict(via=None), 409), ("closed", dict(state="ABANDONED"), 409), ("blocked", dict(state="BLOCKED"), 409),
    ("expired", dict(created=t.NOW - 13 * 3600), 409), ("another kind", dict(kind="issue"), 404),
    ("budget spent", dict(spent_nano=199_000_000), 409), ("turn limit", dict(conversation=[{"from": "human", "text": "x", "at": "x"}] * 200), 409),
])
def test_a_turn_that_may_not_start_is_refused_and_nothing_runs(svc, what, make, status):
    make_session(svc.jobs, **make)
    assert turn(svc)[0] == status and svc.spawner.calls == []
    assert not [a for a in svc.audit() if a.get("attempt") == "manager_turn"]


@pytest.mark.parametrize("message", ["", "   ", "a b", "a b", "a\x00b", "x" * 2001])
def test_a_bad_message_is_refused_at_the_route(svc, message):
    make_session(svc.jobs)
    assert turn(svc, message=message)[0] == 400 and svc.spawner.calls == []


def test_a_busy_session_is_refused(svc):
    make_session(svc.jobs)
    svc.spawner.busy_ids.add(JOB)
    assert turn(svc)[0] == 409 and svc.spawner.calls == []


def test_an_unknown_session_and_a_bad_id_are_refused(svc):
    assert turn(svc, session=JOB)[0] == 404 and turn(svc, session="../x")[0] == 400 and turn(svc, session=JOB + "\n")[0] == 400
    assert svc.spawner.calls == []


def test_the_gates_of_a_post_hold(svc):
    make_session(svc.jobs)
    assert turn(svc, headers={"Origin": "http://evil.example"})[0] == 403
    assert turn(svc, headers={"Sec-Fetch-Site": "same-site"})[0] == 403
    assert turn(svc, host="evil.example")[0] == 421
    assert svc.request("POST", TURN, raw=b"not json")[0] == 400
    assert svc.request("POST", TURN, {"session": JOB, "message": "x", "extra": "1"})[0] == 400
    assert svc.request("POST", TURN, {"session": JOB})[0] == 400
    assert svc.request("POST", TURN, {"session": JOB, "message": 5})[0] == 400
    assert svc.request("POST", TURN, raw=b'{"session": "' + JOB.encode() + b'", "session": "' + JOB.encode() + b'", "message": "x"}')[0] == 400
    assert svc.request("POST", TURN, {"session": JOB, "message": "x"}, headers={"Content-Type": "text/plain"})[0] == 415
    assert svc.spawner.calls == []
    assert svc.request("POST", "/api/manager/other", {"session": JOB})[0] == 405


def test_no_route_hands_a_model_output_to_confirm_or_a_token(svc):
    src = Path(ca.__file__).read_text()
    block = src[src.index("def manager_turn_check"):src.index("def read_manager")]
    assert "confirm" not in block and "prepared" not in block and "token" not in block
    chat_src = Path(sys.modules["router.chat"].__file__).read_text()
    handler = chat_src[chat_src.index("def _manager_turn"):chat_src.index("def _prepare")]
    code = "\n".join(ln for ln in handler.splitlines() if not ln.strip().startswith(('"""', "`argus")) and "No token" not in ln and "was confirmed once" not in ln)
    assert "a.confirm" not in code and "_confirm" not in code and "a.prepare" not in code and "prepared" not in code


# ---- reading --------------------------------------------------------------------------------------------------------------

def test_the_read_route_shows_the_conversation_as_data(svc):
    conv = [{"from": "human", "at": t.iso(t.NOW), "text": "bikin sesuatu"},
            {"from": "manager", "at": t.iso(t.NOW), "say": "oke\x07", "usd": 0.0002, "calls": 1,
             "propose": {"route": "research", "repo": None, "text": "Bandingkan dua pustaka pembukuan untuk Python.", "why": "x"}}]
    make_session(svc.jobs, conversation=conv, spent_nano=2_000)
    status, out = svc.request("GET", f"/api/manager/{JOB}")
    assert status == 200 and out["state"] == "OPEN" and out["spent_usd"] > 0 and 0 < out["expires_in_s"] <= 12 * 3600 and out["busy"] is False
    h, m = out["conversation"]
    assert h == {"from": "human", "n": 0, "at": h["at"], "text": "bikin sesuatu"} and m["n"] == 1
    assert m["source"] == "manager" and "\x07" not in m["say"] and m["propose"]["route"] == "research"
    assert out["turn_cap_usd"] == 0.03 and out["max_turns"] == 200                      # P3: what the page needs to offer a new session
    assert svc.request("GET", "/api/manager/turn")[0] == 404 and svc.request("GET", "/api/manager/j20260101_000000_ffff")[0] == 404


def test_the_read_route_refuses_another_kind(svc):
    t.make_issue(svc.jobs, JOB)
    assert svc.request("GET", f"/api/manager/{JOB}")[0] == 404


def test_the_decision_names_a_session_and_offers_nothing(svc):
    make_session(svc.jobs)
    assert svc.actions.decision(JOB) == {"id": JOB, "kind": "manager", "state": "OPEN"}
    assert JOB not in [r["id"] for r in svc.actions.decisions()["decisions"]]


def test_the_snapshot_keeps_a_session_and_never_its_words(svc):
    raw = {"job": JOB, "kind": "manager", "state": "OPEN", "created_at": t.iso(t.NOW), "max_usd": 0.2,
           "stages": {"m1": {"kind": "manager", "run_id": f"{JOB}-m1", "started_at": t.iso(t.NOW)}},
           "log": [{"at": t.iso(t.NOW), "what": "created", "via": "ui"}, {"at": t.iso(t.NOW), "what": "turn_started"}, {"at": t.iso(t.NOW), "what": "turn_done"},
                   {"at": t.iso(t.NOW), "what": "compaction_started", "covers": "SECRET"}, {"at": t.iso(t.NOW), "what": "compacted", "chars": 1}, {"at": t.iso(t.NOW), "what": "compaction_failed", "reason": "SECRET"},
                   {"at": t.iso(t.NOW), "what": "limits_shown", "screen": "SECRET"}],
           "conversation": [{"from": "human", "text": "PRIVATE WORDS"}], "inputs": {"model": "openrouter:deepseek/deepseek-v4.1-flash-1017"}}
    out = sd.project_job(raw, JOB)
    assert out["kind"] == "manager" and "PRIVATE" not in json.dumps(out) and "SECRET" not in json.dumps(out) and "conversation" not in out


def test_a_session_made_by_the_cli_has_a_known_cost_and_takes_its_first_turn(svc):
    """The chat reads a missing runs directory as an unknown cost (503): the session job must create the stage's directory itself."""
    from router import job as rj2
    jid = rj2.new_job_id()
    svc.clock.t = __import__("time").time()
    mj.new(cfg=svc.actions.cfg, deps=rj2.Deps(clock=lambda: t.iso(svc.clock.t)), jobs_dir=svc.jobs, job_id=jid, via="ui")
    assert svc.actions.read_manager(jid)["spent_usd"] == 0.0
    assert turn(svc, session=jid)[0] == 200


def test_the_read_route_shows_a_summary_as_a_summary_never_as_a_foreman_entry(svc):             # F47-A: SPEC_FOREMAN_MEMORY
    conv = [{"from": "human", "at": t.iso(t.NOW), "text": "a"}, {"from": "manager", "at": t.iso(t.NOW), "say": "b", "usd": 0.0, "calls": 1, "propose": None},
            {"from": "summary", "at": t.iso(t.NOW), "text": "Fakta\x07 penting <b>x</b>", "covers": [0, 2], "usd": 0.0003, "calls": 1, "sha256": "0" * 64,
             "propose": {"route": "issue", "repo": "ledger-cli", "text": "tidak boleh tampil", "why": "x"}, "say": "tidak boleh tampil"},
            {"from": "human", "at": t.iso(t.NOW), "text": "c"}]
    make_session(svc.jobs, conversation=conv)
    status, out = svc.request("GET", f"/api/manager/{JOB}")
    assert status == 200
    s = out["conversation"][2]
    assert s == {"from": "summary", "n": 2, "at": s["at"], "text": s["text"], "covers": [0, 2]} and "\x07" not in s["text"] and "<b>x</b>" in s["text"]       # text only: no say, no proposal, no source
    assert [e["from"] for e in out["conversation"]] == ["human", "manager", "summary", "human"]
    assert out["conversation"][3]["n"] == 3
