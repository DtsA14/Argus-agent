"""SPEC_CHAT_APPLY_REPLY (rev 1, section 12): the three chat actions `prd_reply`, `patch_read_run` and `code_apply` (router/chat_apply.py). Real files in a temporary jobs
directory, a real server on a free port, a fake spawner (no process, no model, no git, no money): what the client may send, what the card shows, the argv that would run, the
refusals, the money the audit counts, and what the foreman cannot do."""
import copy
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_approve_code as tac  # noqa: E402
import test_chat_actions as t  # noqa: E402
import test_chat_t4b as t4  # noqa: E402
from router import chat_actions as ca  # noqa: E402
from router import chat_apply as cap  # noqa: E402
from router import job as rj  # noqa: E402
from router import prd_job as pj  # noqa: E402

CJOB = tac.CJOB
PJOB = "j20261127_100000_aaaa"
READER_KEY = "/keys/reader.key"


def cfg_with_athena(path="~/athena", **chat):
    cfg = t4.make_cfg(**chat)
    cfg["issue_writer"] = copy.deepcopy(cfg["issue_writer"])
    cfg["issue_writer"]["repos"]["athena"] = {"path": path, "environment": "athena_py312"}
    return cfg


@pytest.fixture
def svc(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / "athena").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))                                # the registry says "~/athena", as config.yaml does; a code job records the resolved path
    s = t.Service(tmp_path, cfg=cfg_with_athena())
    s.home = home
    s.queues = tmp_path / "queues"
    s.queues.mkdir()
    s.actions.cards.queues_dir = s.queues
    monkeypatch.setattr(pj, "_repo_state", lambda *a, **k: None)         # the repository's side is the CLI's; a test that wants a refusal patches it again
    yield s
    s.stop()


def prd_job(s, job_id=PJOB, state="AWAITING_HUMAN", via="ui", max_usd=1.5, **kw):
    log = [{"at": t.iso(t.NOW - 100), "what": "created", "via": via}] if via else []
    d = s.jobs / job_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "job.json").write_text(json.dumps({"job": job_id, "kind": "prd", "state": state, "max_usd": max_usd, "created_at": t.iso(t.NOW - 100), "log": log,
                                             "inputs": {"repo": "/secret/path", "repo_name": "athena", "commit": "c" * 40, "environment": "athena_py312"},
                                             "conversation": [], "stages": {}, **kw}))
    return d


def reply(s, **kw):
    return s.prepare(action="prd_reply", job=PJOB, message="ubah rencana: jangan tambah tab keenam", **kw)


def confirm(s, out):
    return s.confirm(out["token"])


def code_job(s, **kw):
    kw.setdefault("by_reader", "argus")
    shutil.rmtree(s.jobs / kw.get("jid", CJOB), ignore_errors=True)               # a test may make the same job again with other contents
    d = tac.make(s, **kw)
    tac.edit_job(d, lambda j: (j["inputs"].pop("repo_name", None), j["inputs"].update(repo=str((s.home / "athena").resolve()))))     # a real code job records the resolved path and no repo_name
    return d


def card(s):
    status, c = tac.get(s)
    assert status == 200
    return c


def two_readings(d, first="ok", second="concerns", ids=("argus:one", "argus:two"), kind="argus", severity=None):
    f = [p for p in d.iterdir() if p.name.startswith("patch_read")][0]
    rec = json.loads(f.read_text())
    rec["verdict"], rec["reader"] = first, {"kind": kind, "id": ids[0]}
    rec["second"] = {"verdict": second, "note": "a detail", "at": "2026-11-18T01:31:00Z", "reader": {"kind": kind, "id": ids[1]}, "template_sha256": rec.get("template_sha256")}
    if severity:
        rec["second"]["severity"] = severity
    f.write_text(json.dumps(rec))


def one_reading(d):
    f = [p for p in d.iterdir() if p.name.startswith("patch_read")][0]
    rec = json.loads(f.read_text())
    rec.pop("second", None)
    f.write_text(json.dumps(rec))


def argv_of(s):
    return s.spawner.calls[-1]["argv"]


def full_sha(s):
    return card(s)["patch_sha256"]


def apply_params(s, **kw):
    return {"action": "code_apply", "job": CJOB, "sha": card(s)["patch_sha12"], **kw}


REASON = "hanya soal nama berkas tes, kodenya benar"


# ---- prd_reply (F28) ----------------------------------------------------------------------------------------------------------------

def test_a_reply_card_shows_the_message_the_cap_and_that_the_plan_is_replaced_and_runs_nothing(svc):
    prd_job(svc)
    status, out = reply(svc)
    assert status == 200 and svc.spawner.calls == []
    c = out["card"]
    assert c["action"] == "prd_reply" and c["job"] == PJOB and c["message"] == "ubah rencana: jangan tambah tab keenam" and c["turn_cap_usd"] == 0.3
    assert c["counted"] is True and out["exposure_usd"] == 0.0 and "replaced" in c["note"] and "lapses" in c["note"]


def test_a_confirmed_reply_runs_the_cli_with_the_message_by_file_via_ui_and_no_other_option(svc):
    prd_job(svc)
    status, out = reply(svc)
    status, body = confirm(svc, out)
    assert status == 200 and body == {"job": PJOB, "started": True}
    call = svc.spawner.calls[-1]
    a = call["argv"]
    i = a.index("prd")
    assert a[i:i + 2] == ["prd", "reply"] and "--message-file" in a and a[a.index("--via") + 1] == "ui" and "--yes" in a
    assert a[a.index("--key-file") + 1] == t.WKEY and a[-2:] == ["--", PJOB]
    assert call["action"] == "prd_reply" and Path(call["message"]).read_text() == "ubah rencana: jangan tambah tab keenam"
    for never in ("--rebase", "--ref", "--max-usd", "--profile", "--message"):
        assert never not in a


def test_a_reply_on_a_job_whose_creation_the_window_does_not_hold_counts_a_turn_and_the_audit_remembers_it_after_ten_minutes(svc):
    prd_job(svc, via=None)
    status, out = reply(svc)
    assert out["card"]["counted"] is False and out["exposure_usd"] == 0.3
    confirm(svc, out)
    assert svc.actions.exposure() == pytest.approx(0.3)
    svc.clock.t += ca.PENDING_S + 60                                    # the list of pending confirms forgets; the audit's attempt line does not (F3)
    assert svc.actions.exposure() == pytest.approx(0.3)
    rec = [r for r in svc.audit() if r.get("action") == "prd_reply" and r.get("attempt") == "confirm"][0]
    assert rec["usd"] == 0.3 and rec["job"] == PJOB
    svc.clock.t += 86400
    assert svc.actions.exposure() == 0.0


@pytest.mark.parametrize("body, status", [
    ({"job": PJOB}, 400), ({"message": "ubah rencananya"}, 400), ({"job": PJOB, "message": "ubah rencananya", "repo": "athena"}, 400),
    ({"job": PJOB, "message": "ubah rencananya", "sha": "a" * 12}, 400), ({"job": PJOB, "message": ""}, 400), ({"job": PJOB, "message": "x" * 2001}, 400),
    ({"job": PJOB, "message": "a‮b"}, 400), ({"job": "../etc", "message": "ubah rencananya"}, 404), ({"job": "j20261127_100001_bbbb", "message": "ubah rencananya"}, 404),
])
def test_a_reply_refuses_a_bad_form_without_a_token(svc, body, status):
    prd_job(svc)
    s, out = svc.prepare(action="prd_reply", **body)
    assert s == status and "token" not in out


@pytest.mark.parametrize("state", ["WRITING", "ABANDONED", "NEW", "BLOCKED"])
def test_a_reply_needs_a_job_that_waits_for_the_human_or_whose_writing_failed(svc, state):
    prd_job(svc, state=state)
    assert reply(svc)[0] == 409


def test_a_reply_is_allowed_after_a_failed_write(svc):
    prd_job(svc, state="WRITE_FAILED")
    assert reply(svc)[0] == 200


def test_a_reply_to_an_issue_job_is_refused_here_and_a_busy_job_too(svc):
    t.make_issue(svc.jobs, PJOB)
    assert reply(svc)[0] == 404
    prd_job(svc, job_id="j20261127_100002_cccc")
    svc.spawner.busy_ids.add("j20261127_100002_cccc")
    assert svc.prepare(action="prd_reply", job="j20261127_100002_cccc", message="ubah rencananya")[0] == 409


def test_a_reply_needs_the_writers_key_and_one_turn_of_budget_and_a_repository_the_cli_would_accept(svc, monkeypatch):
    prd_job(svc, max_usd=0.2)
    assert reply(svc)[0] == 409                                         # $0.2 left < one turn ($0.30)
    prd_job(svc, max_usd=1.5)
    svc.actions.environ = {}
    assert reply(svc)[0] == 409
    svc.actions.environ = {ca.WRITER_KEY_ENV: t.WKEY}
    monkeypatch.setattr(pj, "_repo_state", lambda *a, **k: (_ for _ in ()).throw(rj.Refused("a queue of this repository is not finished; nothing was started")))
    s, out = reply(svc)
    assert s == 409 and "not finished" in json.dumps(out)


def test_a_reply_card_changes_when_the_job_changes_before_the_confirm(svc):
    prd_job(svc)
    status, out = reply(svc)
    prd_job(svc, state="WRITING")
    assert confirm(svc, out)[0] == 409 and svc.spawner.calls == []


def test_the_foreman_cannot_start_a_reply_a_reading_or_an_apply():
    assert set(ca.ROUTE_ACTION) == {"research", "prd"} and not set(cap.ACTIONS) & set(ca.ROUTE_ACTION.values())


@pytest.mark.parametrize("action, extra", [("prd_reply", {"job": PJOB, "message": "ubah rencananya"}), ("patch_read_run", {"job": CJOB}), ("code_apply", {"job": CJOB, "sha": "a" * 12})])
def test_a_proposal_of_the_foreman_cannot_fill_these_forms(svc, action, extra):
    s, out = svc.prepare(action=action, source_job=PJOB, source_turn="1", **extra)
    assert s == 400 and "token" not in out


def test_a_confirm_needs_the_token_the_prepare_gave(svc):
    prd_job(svc)
    assert svc.request("POST", "/api/confirm", {"token": "x" * 43})[0] == 403
    assert svc.request("POST", "/api/confirm", {"action": "prd_reply", "job": PJOB})[0] == 400


# ---- patch_read_run -----------------------------------------------------------------------------------------------------------------

def test_a_reader_card_names_the_two_readers_the_cap_and_the_money_it_can_spend(svc):
    code_job(svc, read=None)
    status, out = svc.prepare(action="patch_read_run", job=CJOB)
    assert status == 200 and svc.spawner.calls == []
    c = out["card"]
    assert c["cap_usd"] == 0.2 and c["billed_usd"] == 0.0 and c["remaining_usd"] == 0.2 and out["exposure_usd"] == 0.2 and c["sha12"] == card(svc)["patch_sha12"]
    assert [r.split(":", 1)[0] for r in c["readers"]] == ["argus", "argus"] and "not a person" in c["note"]


def test_a_confirmed_reading_runs_the_cli_with_the_cap_from_the_config_via_ui_and_the_reader_key(svc):
    code_job(svc, read=None)
    status, out = svc.prepare(action="patch_read_run", job=CJOB)
    status, body = confirm(svc, out)
    assert status == 200 and body == {"job": CJOB, "started": True}
    a = argv_of(svc)
    assert a[a.index("patch-read-run"):a.index("patch-read-run") + 3] == ["patch-read-run", "--cap-usd", "0.2"] and a[a.index("--via") + 1] == "ui" and "--yes" in a
    assert a[a.index("--key-file") + 1] == t.KEY and a[-2:] == ["--", CJOB]
    for never in ("--first", "--second", "--max-output"):
        assert never not in a
    rec = [r for r in svc.audit() if r.get("action") == "patch_read_run" and r.get("attempt") == "confirm"][0]
    assert rec["usd"] == 0.2 and rec["job"] == CJOB


def test_the_readers_have_their_own_key_slot_and_fall_back_to_the_code_key(svc):
    code_job(svc, read=None)
    svc.actions.environ = {ca.KEY_ENV: t.KEY, ca.READER_KEY_ENV: READER_KEY}
    confirm(svc, svc.prepare(action="patch_read_run", job=CJOB)[1])
    assert argv_of(svc)[argv_of(svc).index("--key-file") + 1] == READER_KEY
    svc.actions.environ = {ca.WRITER_KEY_ENV: t.WKEY}
    s, out = svc.prepare(action="patch_read_run", job=CJOB)
    assert s == 409 and "ARGUS_CHAT_READER_KEY_FILE" in json.dumps(out)


@pytest.mark.parametrize("bad", [5, -1, 0, "x", True, None, float("inf")])
def test_a_cap_in_the_config_that_is_not_above_zero_and_at_most_two_is_the_default(svc, bad):
    svc.actions._cfg = cfg_with_athena(patch_read_cap_usd=bad)
    assert svc.actions.apply_reply.read_cap() == 0.2
    svc.actions._cfg = cfg_with_athena(patch_read_cap_usd=0.5)
    assert svc.actions.apply_reply.read_cap() == 0.5


def test_the_client_cannot_send_a_cap_or_a_reader_or_anything_but_the_job(svc):
    code_job(svc, read=None)
    for extra in ({"cap": "5"}, {"first": "x"}, {"sha": "a" * 12}, {"message": "x"}):
        s, out = svc.prepare(action="patch_read_run", job=CJOB, **extra)
        assert s == 400 and "token" not in out


def test_a_final_reading_state_or_a_busy_run_or_a_spent_cap_refuses_a_reading(svc, monkeypatch):
    d = code_job(svc, read="ok")
    assert svc.prepare(action="patch_read_run", job=CJOB)[0] == 409                  # two `ok`: nothing is read again
    two_readings(d, "concerns", "concerns")
    assert svc.prepare(action="patch_read_run", job=CJOB)[0] == 409                  # a concern of both readers is final too
    one_reading(d)
    assert svc.prepare(action="patch_read_run", job=CJOB)[0] == 409                  # a lone `concerns` of another reader than the first of the pair: the run would read nothing
    from router import patch_read_run as prr
    two_readings(d, "concerns", "concerns", ids=(prr.reader_id(prr.FIRST), "argus:other"))
    one_reading(d)
    assert svc.prepare(action="patch_read_run", job=CJOB)[0] == 200                  # the first reader's own `concerns` with no second: only the second is asked (`resume`)
    two_readings(d, "concerns", "concerns", ids=("claude-1", "claude-2"), kind="claude")
    one_reading(d)
    assert svc.prepare(action="patch_read_run", job=CJOB)[0] == 409                  # a Claude reading is not resumed: the run reads nothing, so the page must not offer it
    code_job(svc, read=None)
    assert svc.prepare(action="patch_read_run", job=CJOB)[0] == 200                  # no reading at all
    svc.spawner.busy_ids.add(CJOB)
    assert svc.prepare(action="patch_read_run", job=CJOB)[0] == 409
    svc.spawner.busy_ids.clear()
    monkeypatch.setattr(cap.ApplyReply, "_billed", lambda self, j: (0.25, True))
    assert svc.prepare(action="patch_read_run", job=CJOB)[0] == 409                  # billed more than the cap
    monkeypatch.setattr(cap.ApplyReply, "_billed", lambda self, j: (0.05, False))
    assert svc.prepare(action="patch_read_run", job=CJOB)[0] == 409                  # a ledger with a call without a price
    monkeypatch.setattr(cap.ApplyReply, "_billed", lambda self, j: (0.15, True))
    s, out = svc.prepare(action="patch_read_run", job=CJOB)
    assert s == 200 and out["card"]["remaining_usd"] == pytest.approx(0.05) and out["exposure_usd"] == pytest.approx(0.05)


def test_a_job_that_is_not_review_ready_gets_no_reading(svc):
    code_job(svc, read=None, state="AWAITING_APPROVAL")
    assert svc.prepare(action="patch_read_run", job=CJOB)[0] == 409
    assert svc.prepare(action="patch_read_run", job="j20261127_111111_dddd")[0] == 404


def test_the_readers_run_at_most_twice_for_a_job_in_24_hours(svc):
    code_job(svc, read=None)
    for _ in range(2):
        s, out = svc.prepare(action="patch_read_run", job=CJOB)
        assert s == 200
        assert confirm(svc, out)[0] == 200
        svc.spawner.busy_ids.clear()
    s, out = svc.prepare(action="patch_read_run", job=CJOB)
    assert s == 409 and "2 times" in json.dumps(out)
    svc.clock.t += 86400 + 10
    assert svc.prepare(action="patch_read_run", job=CJOB)[0] == 200


def test_the_limit_counts_the_job_and_the_money_of_a_reading_counts_to_the_daily_cap(svc):
    code_job(svc, read=None)
    other = "j20261127_120000_eeee"
    code_job(svc, jid=other, read=None)
    for _ in range(2):
        s, out = svc.prepare(action="patch_read_run", job=CJOB)
        assert s == 200 and confirm(svc, out)[0] == 200
        svc.spawner.busy_ids.clear()
    assert svc.prepare(action="patch_read_run", job=CJOB)[0] == 409                    # this job is at its two
    assert svc.prepare(action="patch_read_run", job=other)[0] == 200                   # another job has its own count (per job, not per action)
    prd_job(svc, via=None)
    confirm(svc, reply(svc)[1])
    svc.spawner.busy_ids.clear()
    assert svc.prepare(action="patch_read_run", job=other)[0] == 200                   # a PRD reply is not a reading
    assert svc.actions.exposure() == pytest.approx(2 * 0.2 + 0.3)
    svc.clock.t += ca.PENDING_S + 60
    assert svc.actions.exposure() == pytest.approx(2 * 0.2 + 0.3)                      # still, from the audit


def test_a_reading_that_would_pass_the_daily_cap_is_refused_at_prepare(svc):
    svc.actions._cfg = cfg_with_athena(daily_cap_usd=0.1)
    code_job(svc, read=None)
    s, out = svc.prepare(action="patch_read_run", job=CJOB)
    assert s == 403 and "daily cap" in json.dumps(out)


# ---- code_apply ---------------------------------------------------------------------------------------------------------------------

def test_an_apply_card_shows_the_files_the_readings_as_written_the_target_and_the_declaration_and_runs_nothing(svc):
    code_job(svc)
    c0 = card(svc)
    status, out = svc.prepare(**apply_params(svc))
    assert status == 200 and svc.spawner.calls == [] and out["exposure_usd"] == 0.0
    c = out["card"]
    assert c["action"] == "code_apply" and c["job"] == CJOB and c["sha12"] == c0["patch_sha12"] and c["repo"] == "athena"
    assert [f["path"] for f in c["files"]] == ["src/shop.py"] and c["patch_read"]["verdict"] == "ok" and c["patch_read"]["second"]["verdict"] == "ok"
    assert c["declaration"].endswith("not a proof that it was read") and "not pushed, not deployed" in c["note"]
    assert c["target_branch"] in (None, f"argus/{CJOB}") or c["branch"] not in ("main", "master")


def test_a_confirmed_apply_runs_the_cli_with_the_full_sha_the_argus_reader_via_ui_and_nothing_else(svc):
    code_job(svc)
    full = full_sha(svc)
    status, out = svc.prepare(**apply_params(svc))
    status, body = confirm(svc, out)
    assert status == 200 and body == {"job": CJOB, "started": True}
    a = argv_of(svc)
    i = a.index("apply")
    assert a[i:] == ["apply", "--read-sha", full, "--reader", "argus", "--via", "ui", "--", CJOB] and "--key-file" not in a and "--yes" not in a
    for never in ("--allow-failed-examples", "--note", "--accept-concerns"):
        assert not any(x.startswith(never) for x in a)
    assert svc.spawner.calls[-1]["action"] == "code_apply"
    rec = [r for r in svc.audit() if r.get("action") == "code_apply" and r.get("attempt") == "confirm"][0]
    assert rec["usd"] == 0.0 and rec["sha"] == full[:12] and rec["job"] == CJOB


@pytest.mark.parametrize("extra, status", [
    ({"repo": "athena"}, 400), ({"cap": "1"}, 400), ({"message": "x"}, 400), ({"queue": "q"}, 400), ({"ack": "y"}, 400), ({"reason": REASON}, 400)])
def test_the_client_sends_the_job_the_seen_sha_and_for_a_concern_the_reason_and_nothing_else(svc, extra, status):
    code_job(svc)
    s, out = svc.prepare(**apply_params(svc, **extra))
    assert s == status and "token" not in out


def test_a_missing_or_short_or_other_sha_is_refused_and_it_is_a_check_never_a_selector(svc):
    code_job(svc)
    p = apply_params(svc)
    for sha in (None, "", "abc", "z" * 12, "0" * 12, p["sha"].upper(), p["sha"] + "0"):
        body = {k: v for k, v in p.items() if k != "sha"} if sha is None else {**p, "sha": sha}
        s, out = svc.prepare(**body)
        assert s in (400, 409) and "token" not in out
    assert svc.prepare(**p)[0] == 200


def test_the_sha_param_is_refused_for_other_actions_but_not_for_code_apply(svc):
    prd_job(svc)
    assert svc.prepare(action="prd_reply", job=PJOB, message="ubah rencananya", sha="a" * 12)[0] == 400
    assert svc.prepare(action="patch_read_run", job=CJOB, sha="a" * 12)[0] == 400
    code_job(svc)
    assert svc.prepare(**apply_params(svc))[0] == 200


def test_a_patch_that_changed_after_the_card_was_shown_is_refused_at_prepare_and_at_confirm(svc):
    d = code_job(svc)
    p = apply_params(svc)
    status, out = svc.prepare(**p)
    run = d / "runs" / f"{CJOB}-a1" / "review"
    (run / "changes.patch").write_bytes(tac.build_patch(["src/shop.py"], {"src/shop.py": "z"}))
    assert confirm(svc, out)[0] == 409 and svc.spawner.calls == []
    s, out2 = svc.prepare(**p)
    assert s == 409 and "token" not in out2 and "(g)" in json.dumps(out2)          # the card's own condition: review, provenance and disk no longer name one patch


def test_a_closed_condition_of_the_card_refuses_the_apply_and_says_which(svc):
    code_job(svc, audit="fail")
    s, out = svc.prepare(**apply_params(svc))
    assert s == 409 and "token" not in out and "(" in json.dumps(out)


def test_a_reading_written_by_a_claude_session_is_not_applied_from_here(svc):
    code_job(svc, by_reader="claude")
    s, out = svc.prepare(**apply_params(svc))
    assert s == 409 and "Claude" in json.dumps(out)


def test_no_second_reading_means_the_readers_are_run_first(svc):
    d = code_job(svc)
    one_reading(d)
    s, out = svc.prepare(**apply_params(svc))
    assert s == 409 and "two final readings" in json.dumps(out)
    code_job(svc, read=None)
    assert svc.prepare(action="code_apply", job=CJOB, sha="0" * 12)[0] in (409,)


def test_a_concern_needs_the_humans_typed_reason_which_goes_as_one_token_and_only_its_hash_is_audited(svc):
    d = code_job(svc)
    two_readings(d)
    p = apply_params(svc)
    assert svc.prepare(**p)[0] == 400                                                       # no reason
    for bad in ("short", "x" * 501, "a\nb" + "c" * 10, "sk-ant-" + "a" * 30 + " leaked key text", 5):
        s, out = svc.prepare(**{**p, "reason": bad})
        assert s == 400 and "token" not in out
    status, out = svc.prepare(**{**p, "reason": REASON})
    assert status == 200 and out["card"]["accepted_concerns"] is True and out["card"]["reason"] == REASON
    status, body = confirm(svc, out)
    a = argv_of(svc)
    assert f"--accept-concerns={REASON}" in a and "--accept-concerns" not in a and a[-2:] == ["--", CJOB]
    rec = [r for r in svc.audit() if r.get("action") == "code_apply" and r.get("attempt") == "confirm"][0]
    assert rec["reason_sha256"] == hashlib.sha256(REASON.encode()).hexdigest() and REASON not in json.dumps(svc.audit())


def test_a_reason_that_starts_with_a_dash_stays_one_token(svc):
    d = code_job(svc)
    two_readings(d)
    status, out = svc.prepare(**{**apply_params(svc), "reason": "-" + REASON})
    assert status == 200
    confirm(svc, out)
    assert f"--accept-concerns=-{REASON}" in argv_of(svc)


def test_a_concern_of_one_reader_alone_or_by_the_same_reader_twice_cannot_be_accepted(svc):
    d = code_job(svc)
    two_readings(d, ids=("argus:same", "argus:same"))
    assert svc.prepare(**{**apply_params(svc), "reason": REASON})[0] == 409
    two_readings(d, "concerns", "concerns")
    one_reading(d)
    assert svc.prepare(**{**apply_params(svc), "reason": REASON})[0] == 409


def test_a_reason_with_two_ok_readings_is_refused_because_there_is_nothing_to_accept(svc):
    code_job(svc)
    assert svc.prepare(**{**apply_params(svc), "reason": REASON})[0] == 400


def test_a_nit_pair_is_applied_like_ok(svc):
    from router import patch_read_run as prr
    d = code_job(svc)
    ids = (prr.reader_id(prr.FIRST), prr.reader_id(prr.SECOND))
    two_readings(d, "concerns", "concerns", ids=ids)
    f = [p for p in d.iterdir() if p.name.startswith("patch_read")][0]
    rec = json.loads(f.read_text())
    rec["severity"] = rec["second"]["severity"] = "nit"
    f.write_text(json.dumps(rec))
    assert card(svc)["patch_read_kind"] == "nit"
    status, out = svc.prepare(**apply_params(svc))
    assert status == 200 and "accepted_concerns" not in out["card"]
    assert svc.prepare(**{**apply_params(svc), "reason": REASON})[0] == 400              # a nit pair needs no reason


def test_the_repository_is_found_by_path_with_the_tilde_expanded_and_a_real_job_has_no_repo_name(svc):
    d = code_job(svc)
    assert "repo_name" not in json.loads((d / "job.json").read_text())["inputs"]
    s, out = svc.prepare(**apply_params(svc))
    assert s == 200 and out["card"]["repo"] == "athena" and "repo_path" not in out["card"] and "/home" not in json.dumps(out["card"])
    assert out["card"]["repo_realpath_sha256"] == hashlib.sha256(str((svc.home / "athena").resolve()).encode()).hexdigest()


def test_the_repository_must_be_the_registered_one_and_never_argus_itself(svc):
    d = code_job(svc)
    tac.edit_job(d, lambda j: j["inputs"].update(repo="/elsewhere"))
    assert svc.prepare(**apply_params(svc))[0] == 409
    tac.edit_job(d, lambda j: j["inputs"].update(repo=str(rj.ROOT)))
    svc.actions._cfg = cfg_with_athena(path=str(rj.ROOT))
    s, out = svc.prepare(**apply_params(svc))
    assert s == 409 and "Argus itself" in json.dumps(out)
    tac.edit_job(d, lambda j: j["inputs"].update(repo=str(rj.ROOT / "router")))                  # a subdirectory of the checkout is Argus too
    svc.actions._cfg = cfg_with_athena(path=str(rj.ROOT / "router"))
    s, out = svc.prepare(**apply_params(svc))
    assert s == 409 and "Argus itself" in json.dumps(out)
    svc.actions._cfg = cfg_with_athena()
    tac.edit_job(d, lambda j: j["inputs"].update(repo=str((svc.home / "athena").resolve())))
    assert svc.prepare(**apply_params(svc))[0] == 200
    cfg = cfg_with_athena()
    cfg["issue_writer"]["repos"]["twin"] = {"path": str(svc.home / "athena"), "environment": "x"}      # two names for one repository: not exactly one entry
    svc.actions._cfg = cfg
    assert svc.prepare(**apply_params(svc))[0] == 409
    svc.actions._cfg = cfg_with_athena(path="~/other")
    assert svc.prepare(**apply_params(svc))[0] == 409


def test_a_patch_the_page_cannot_show_whole_or_as_it_is_is_not_applied_from_here(svc):
    code_job(svc, bodies={"src/shop.py": "ok‮evil"})                                    # a bidirectional override in an added line
    s, out = svc.prepare(**apply_params(svc))
    assert s == 409 and "characters" in json.dumps(out)
    code_job(svc, bodies={"src/shop.py": "A" * (cap.PATCH_TEXT_MAX + 10)})
    s, out = svc.prepare(**apply_params(svc))
    assert s == 409 and "too large" in json.dumps(out)


def test_the_diff_route_gives_the_whole_patch_as_text_or_why_it_cannot_and_changes_nothing(svc):
    code_job(svc)
    status, out = svc.request("GET", f"/api/diff/{CJOB}")
    assert status == 200 and out["text"].startswith("diff --git") and out["sha12"] == card(svc)["patch_sha12"] and out["why"] is None
    code_job(svc, bodies={"src/shop.py": "ok‮evil"})
    status, out = svc.request("GET", f"/api/diff/{CJOB}")
    assert status == 200 and out["text"] is None and "characters" in out["why"]
    assert svc.request("GET", "/api/diff/not-a-job")[0] == 404 and svc.spawner.calls == []
    for path in ("/api/diff", f"/api/diff/{CJOB}"):
        assert svc.request("POST", path, {"action": "patch_read_run", "job": CJOB})[0] == 405          # GET only: a POST route list that named the diff would prepare an action here


def test_a_busy_job_and_a_job_not_review_ready_are_refused(svc):
    code_job(svc)
    svc.spawner.busy_ids.add(CJOB)
    assert svc.prepare(**apply_params(svc))[0] == 409
    svc.spawner.busy_ids.clear()
    code_job(svc, state="APPLIED")
    s, out = svc.prepare(action="code_apply", job=CJOB, sha="0" * 12)
    assert s == 409


def test_the_install_card_tells_the_page_which_button_to_offer(svc):
    code_job(svc, read=None)
    assert card(svc)["apply"] == {"action": "patch_read_run", "why": None}
    d = code_job(svc)
    assert card(svc)["apply"] == {"action": "code_apply", "why": None, "needs_reason": False}
    two_readings(d)
    assert card(svc)["apply"] == {"action": "code_apply", "why": None, "needs_reason": True}
    code_job(svc, audit="fail")
    a = card(svc)["apply"]
    assert a["action"] is None and a["why"]


def test_a_card_that_cannot_be_made_is_a_refusal_never_a_pass(svc, monkeypatch):
    code_job(svc)
    p = apply_params(svc)
    monkeypatch.setattr(type(svc.actions.approve_code), "_code", lambda self, *a, **k: (_ for _ in ()).throw(OSError("boom")))
    s, out = svc.prepare(**p)
    assert s == 404 and svc.spawner.calls == []
    assert svc.request("GET", f"/api/approve/code/{CJOB}")[0] == 404


def test_the_cli_runs_are_started_through_the_spawner_and_not_inside_the_request(svc):
    code_job(svc)
    status, out = svc.prepare(**apply_params(svc))
    confirm(svc, out)
    assert len(svc.spawner.calls) == 1 and svc.runs == []                               # no synchronous control CLI: the spawner holds the run, the page reads the job file


def test_the_apply_card_binds_the_sid_the_full_sha_the_kind_and_every_check_so_a_change_in_any_of_them_is_a_409_at_confirm(svc):
    d = code_job(svc)
    status, out = svc.prepare(**apply_params(svc))
    c = out["card"]
    assert c["sid"] == "a1" and len(c["patch_sha256"]) == 64 and c["patch_read_kind"] == "ok" and {x["key"] for x in c["checks"]} == set("abcdefghi")
    tac.edit_job(d, lambda j: j.pop("approval"))                                    # conditions (d) and (e) change from True/None to another value
    status2, _ = confirm(svc, out)
    assert status2 == 409 and svc.spawner.calls == []


def test_the_reader_card_binds_the_sid_and_the_full_sha(svc):
    code_job(svc, read=None)
    c = svc.prepare(action="patch_read_run", job=CJOB)[1]["card"]
    assert c["sid"] == "a1" and c["patch_sha256"] == full_sha(svc)


def test_the_card_names_the_target_branch_as_the_command_will_choose_it_and_says_when_there_is_none(svc, monkeypatch):
    code_job(svc)
    for state, target in ((("main", "h" * 40, True), f"argus/{CJOB}"), (("develop", "h" * 40, True), f"argus/{CJOB}"), (("feature", "h" * 40, False), "feature")):
        monkeypatch.setattr(cap.ApplyReply, "_git_state", lambda self, repo, st=state: st)
        c = svc.prepare(**apply_params(svc))[1]["card"]
        assert c["target_branch"] == target and c["detached_note"] is None
    monkeypatch.setattr(cap.ApplyReply, "_git_state", lambda self, repo: (None, None, None))
    c = svc.prepare(**apply_params(svc))[1]["card"]
    assert c["target_branch"] is None and "detached" in c["detached_note"]


def test_one_get_of_the_install_card_builds_it_once_for_the_button(svc, monkeypatch):
    code_job(svc)
    n = {"c": 0}
    real = type(svc.actions.approve_code)._code

    def counting(self, *a, **k):
        n["c"] += 1
        return real(self, *a, **k)
    monkeypatch.setattr(type(svc.actions.approve_code), "_code", counting)
    assert svc.request("GET", f"/api/approve/code/{CJOB}")[0] == 200
    assert n["c"] == 2                                                              # the card itself, and the one the button decision reads (not four)


def test_git_is_asked_with_a_short_timeout_and_a_hung_repository_gives_no_state_not_a_stall(svc, monkeypatch):
    from router import apply as ra
    seen = []

    def run_git(repo, *a, **k):
        seen.append(k.get("timeout"))
        raise OSError("hung")
    monkeypatch.setattr(ra, "run_git", run_git)
    assert svc.actions.apply_reply._git_state("/x") == (None, None, None) and seen and all(x == cap.GIT_TIMEOUT_S for x in seen)


def ledger_events(usd_nano=40_000_000, final=True):
    ev = [{"event": "llm_call_started", "call_id": "c1", "worst_usd_nano": 90_000_000, "worst_tokens": 10}]
    if final:
        ev.append({"event": "llm_call", "call_id": "c1", "status": "ok", "usd_nano": usd_nano, "tokens": 10})
    return "\n".join(json.dumps(e) for e in ev) + "\n"


def test_the_billed_money_is_read_from_a_real_ledger_through_the_job_directory(svc):
    code_job(svc, read=None)
    (svc.jobs / CJOB / "patch_read_ledger.jsonl").write_text(ledger_events())
    assert svc.actions.apply_reply._billed(CJOB) == (pytest.approx(0.04), True)
    c = svc.prepare(action="patch_read_run", job=CJOB)[1]["card"]
    assert c["billed_usd"] == pytest.approx(0.04) and c["remaining_usd"] == pytest.approx(0.16)
    (svc.jobs / CJOB / "patch_read_ledger.jsonl").write_text(ledger_events(final=False))            # a call that never finished is charged at its worst case
    assert svc.actions.apply_reply._billed(CJOB) == (pytest.approx(0.09), True)


def test_a_ledger_that_is_a_link_or_damaged_or_missing_is_handled_without_following_it(svc, tmp_path):
    code_job(svc, read=None)
    assert svc.actions.apply_reply._billed(CJOB) == (0.0, True)                                     # no ledger: nothing billed
    outside = tmp_path / "outside.jsonl"
    outside.write_text(ledger_events())
    (svc.jobs / CJOB / "patch_read_ledger.jsonl").symlink_to(outside)
    s, out = svc.prepare(action="patch_read_run", job=CJOB)
    assert s == 503 and "ledger" in json.dumps(out)
    (svc.jobs / CJOB / "patch_read_ledger.jsonl").unlink()
    (svc.jobs / CJOB / "patch_read_ledger.jsonl").write_text("not json\n")
    assert svc.prepare(action="patch_read_run", job=CJOB)[0] == 503


def test_a_huge_integer_cap_in_the_config_is_the_default_not_a_crash(svc):
    svc.actions._cfg = cfg_with_athena(patch_read_cap_usd=10 ** 400)
    assert svc.actions.apply_reply.read_cap() == 0.2


def test_an_audit_line_with_a_bad_time_or_amount_is_a_503_at_prepare_never_a_500_and_never_skipped(svc):
    code_job(svc, read=None)
    svc.actions.audit_path.parent.mkdir(parents=True, exist_ok=True)
    for bad in ({"action": "patch_read_run", "attempt": "confirm", "at": "not a time", "usd": 0.2}, {"action": "prd_reply", "attempt": "confirm", "at": t.iso(t.NOW), "usd": "x"}):
        svc.actions.audit_path.write_text(json.dumps(bad) + "\n")
        s, out = svc.prepare(action="patch_read_run", job=CJOB)
        assert s == 503 and "cannot be computed" in json.dumps(out)


def test_the_limit_counts_only_the_readings_of_the_job_not_its_applies_or_replies(svc):
    code_job(svc, read=None)
    svc.actions.audit_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [{"action": a, "attempt": "confirm", "at": t.iso(svc.clock()), "job": CJOB, "usd": 0.0} for a in ("code_apply", "code_apply", "prd_reply", "issue_reply")]
    svc.actions.audit_path.write_text("".join(json.dumps(x) + "\n" for x in lines))
    assert svc.prepare(action="patch_read_run", job=CJOB)[0] == 200


def test_a_draft_sha_is_refused_by_the_http_layer_for_every_action_but_a_job_decision_and_code_apply(svc):
    s, out = svc.prepare(action="issue_new", repo="argus-viewer", message="tambahkan tombol", sha="a" * 12)
    assert s == 400 and "only a decision of a job takes a draft sha" in json.dumps(out)


def test_the_card_the_apply_reads_holds_no_patch_text(svc):
    code_job(svc)
    card_, raw, disk = svc.actions.approve_code.code_with_patch(CJOB)
    assert raw and b"diff --git" in raw and "diff --git" not in json.dumps(card_) and disk == card_["patch_sha256"]


def test_the_button_state_says_why_a_reading_cannot_be_offered(svc):
    code_job(svc, read=None)
    svc.actions.environ = {ca.WRITER_KEY_ENV: t.WKEY}                                # no key for the readers
    a = card(svc)["apply"]
    assert a["action"] is None and "ARGUS_CHAT_READER_KEY_FILE" in a["why"]
