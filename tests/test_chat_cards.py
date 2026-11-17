"""SPEC_CHAT_CARDS rev 1 (T2): read-only cards for PRD jobs, queues and the examples of an issue. Real files in a temporary jobs and queues
directory, a real server on a free port for the routes; no model, no Docker, no process (subprocess and fork are patched to raise)."""
import hashlib
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_chat_actions import CFG, Service  # noqa: E402

from codetask import examples as ex  # noqa: E402
from router import cards as rcards  # noqa: E402
from router import example_gate as eg  # noqa: E402
from router import prd as rp  # noqa: E402
from router import queue as rq  # noqa: E402

PJOB, IJOB, CJOB1, CJOB2 = "j20261117_100000_aaaa", "j20261117_100100_bbbb", "j20261117_100200_cccc", "j20261117_100300_dddd"
QID = "q20261117T100400Z-abcd"
SAME = {"id": "e1", "tier": "same", "says": "Two prices and a discount of 1 give 4", "setup": "from src.shop import total",
        "run": "total([2, 3], 1)", "expect": 4}
AFTER = {"id": "e2", "tier": "after", "says": "A discount larger than the sum floors at 0", "setup": "from src.shop import total",
         "run": "total([1], 5)", "expect": 0}
ISSUE = "total() never goes below zero\n\nA discount larger than the sum gives 0.\n\nNothing else changes: x\n\nTests: y\n\nEnvironment: pyenv"


def issue_text(*examples, title="total() never goes below zero"):
    return eg.with_block(ISSUE.replace("total() never goes below zero", title), list(examples))


def results_for(examples, **status):
    return [{"id": e["id"], "tier": e["tier"], "status": status.get(e["id"], "pass" if e["tier"] != "after" else "unchecked"),
             **({"base_actual": -4} if e["tier"] == "after" else {"actual": e["expect"] if "expect" in e else "x"})} for e in examples]


def stored_for(examples, **kw):
    return {"examples": examples, "results": results_for(examples, **kw), "no_examples": None, "note": None, "tier_moves": []}


def write_job(jobs, job_id, **data):
    d = jobs / job_id
    d.mkdir(parents=True, exist_ok=True)
    base = {"job": job_id, "state": "AWAITING_HUMAN", "max_usd": 1.0, "created_at": "2026-11-17T10:00:00Z",
            "inputs": {"repo": "/secret/path", "repo_name": "athena", "commit": "c" * 40, "environment": "athena_py312"},
            "stages": {}, "log": []}
    (d / "job.json").write_text(json.dumps({**base, **data}))
    return d


def write_prd(jobs, texts, examples_per_item, **turn):
    """A PRD job with one folder prd-w1 made of `texts`; the turn records the sha of the folder as the job did."""
    files = {"PRD.md": b"Goal: x.\nThe contract: y.\n", "issues.json": json.dumps({"repo": "athena", "items": [{"n": i} for i in range(1, len(texts) + 1)]}).encode()}
    for n, t in enumerate(texts, 1):
        files[f"issue-{n}.md"] = t.encode()
    d = write_job(jobs, PJOB, kind="prd", conversation=[{"from": "human", "text": "bikin dua perubahan\nlagi"},
                                                         {"from": "writer", "text": "ok", "questions": ["pakai jam?"]}],
                  prd_turns=[{"turn": "w1", "folder_sha": rp.folder_sha(files), "commit": "c" * 40, "items": len(texts),
                              "examples": examples_per_item, "touches": [["def total"]] * len(texts), "creates": [["show_floor"], []][:len(texts)],
                              "clashes": [[{"file": "tests/test_a.py", "line": 3, "why": "reads it"}], []][:len(texts)],
                              "warnings": ["a warning"], "max_usd": 2.0, **turn}],
                  stages={"w1": {"kind": "write", "run_id": f"{PJOB}-w1", "usd": 0.05}})
    f = d / "prd-w1"
    f.mkdir(exist_ok=True)
    for name, data in files.items():
        (f / name).write_bytes(data)
    return d, files


@pytest.fixture
def svc(tmp_path):
    s = Service(tmp_path)
    s.queues = tmp_path / "queues"
    s.queues.mkdir()
    s.actions.cards.queues_dir = s.queues
    yield s
    s.stop()


def card(s, kind, id_):
    return s.request("GET", f"/api/cards/{kind}/{id_}")


def write_queue(s, items, **kw):
    d = s.queues / QID
    d.mkdir(exist_ok=True)
    texts = {}
    entries = []
    for n, (text, job) in enumerate(items, 1):
        (d / f"issue-{n}.md").write_text(text)
        texts[n] = text
        entries.append({"n": n, "issue_sha256": hashlib.sha256(text.encode()).hexdigest(), "job": job})
    q = {"id": QID, "repo": "/secret/path", "name": "athena", "base_commit": "c" * 40, "jobs_dir": str(s.jobs), "max_usd": 2.0,
         "job_cap_usd": 0.5, "environment": "athena_py312", "items": entries, **kw}
    (d / "queue.json").write_text(json.dumps(q))
    return d, texts


def code_job(s, job_id, text, state="REVIEW_READY", examples=None, **kw):
    d = write_job(s.jobs, job_id, kind="code", state=state, inputs={"repo": "/secret/path", "repo_name": "athena", "commit": "c" * 40,
                                                                    "issue": text, "environment": "athena_py312"},
                  intake={"snapshot_sha256": "5" * 64}, stages={"a1": {"kind": "agent", "review": {"patch_sha256": "7" * 64}}}, **kw)
    return d


# ---- PRD cards ----------------------------------------------------------------------------------------------------------------

def test_a_prd_card_has_the_status_from_the_turn_and_the_calls_from_the_block_and_the_model_text_apart(svc):
    t1, t2 = issue_text(SAME, AFTER, title="Floor the total"), issue_text(title="Show it")
    write_prd(svc.jobs, [t1, t2], [stored_for([SAME, AFTER]), None])
    status, c = card(svc, "prd", PJOB)
    assert status == 200 and c["state"] == "AWAITING_HUMAN" and c["turn"] == "w1" and c["stale"] is False and c["superseded"] is False
    first = c["items"][0]
    assert first["title"] == "Floor the total" and "argus-examples" not in first["text"] and "Nothing else changes" in first["text"]
    ex1 = first["examples"]
    assert [(r["id"], r["status"], r["where"]) for r in ex1["results"]] == [("e1", "pass", "penulis"), ("e2", "unchecked", "penulis")]
    assert ex1["calls"][0]["says"].startswith("Two prices") and ex1["calls"][0]["run"] == "total([2, 3], 1)" and ex1["calls"][0]["expect"] == "4"
    assert "says" not in ex1["results"][0] and ex1["results"][1]["base_actual"] == "-4"
    assert c["prd_md"].startswith("Goal: x.") and c["questions"] == ["pakai jam?"] and c["money"]["queue_usd"] == 2.0 and c["money"]["spent"] == 0.05
    assert first["touches"] == ["def total"] and first["creates"] == ["show_floor"] and first["clashes"][0]["file"] == "tests/test_a.py"


def test_an_item_the_writer_did_not_run_is_not_run_until_its_code_job_ran(svc):
    t1, t2 = issue_text(SAME), issue_text(AFTER, title="Second")
    write_prd(svc.jobs, [t1, t2], [stored_for([SAME]), {"examples": [AFTER], "results": [], "no_examples": None, "note": None, "tier_moves": []}])
    c = card(svc, "prd", PJOB)[1]
    second = c["items"][1]["examples"]
    assert [(r["id"], r["status"]) for r in second["results"]] == [("e2", rcards.NOT_RUN)] and second["why"] == rcards.NOT_RUN_WHY


def test_a_status_is_never_shown_for_a_file_that_is_not_the_one_it_was_computed_for(svc):
    t1 = issue_text(SAME)
    d, files = write_prd(svc.jobs, [t1], [stored_for([SAME])])
    (d / "prd-w1" / "issue-1.md").write_text(issue_text({**SAME, "expect": 5}))             # the folder changed after the turn
    c = card(svc, "prd", PJOB)[1]
    assert c["items"][0]["examples"]["results"] is None and c["items"][0]["examples"]["why"] == "berkas tidak cocok dengan hasil"
    d2, _ = write_prd(svc.jobs, [t1], [stored_for([{**SAME, "expect": 7}])])               # results of other examples than the block's
    (d2 / "prd-w1" / "issue-1.md").write_text(t1)
    assert card(svc, "prd", PJOB)[1]["items"][0]["examples"]["results"] is None


def test_the_turn_name_is_checked_before_a_directory_is_opened(svc, tmp_path):
    outside = svc.jobs / "x"
    outside.mkdir()
    d, _ = write_prd(svc.jobs, [issue_text(SAME)], [stored_for([SAME])])
    j = json.loads((d / "job.json").read_text())
    j["prd_turns"][0]["turn"] = "../x"
    (d / "job.json").write_text(json.dumps(j))
    c = card(svc, "prd", PJOB)[1]
    assert c["items"] == [] and c["why"] == "nama giliran tidak sah"


def test_a_stale_and_a_superseded_folder_are_flagged_and_an_old_turn_has_no_examples(svc):
    d, _ = write_prd(svc.jobs, [issue_text(SAME)], None)
    j = json.loads((d / "job.json").read_text())
    del j["prd_turns"][0]["examples"]
    j["prd_turns"][0]["commit"] = "d" * 40                                                    # another commit than the job's
    (d / "job.json").write_text(json.dumps(j))
    (d / "prd-w1" / "SUPERSEDED").write_text("replaced\n")
    c = card(svc, "prd", PJOB)[1]
    assert c["stale"] is True and c["superseded"] is True and c["commit12"] == "d" * 12
    assert c["items"][0]["examples"]["why"] == "dari sebelum gerbang contoh" and c["items"][0]["examples"]["results"] is None


def test_a_prd_job_without_a_folder_yet_and_a_job_of_another_kind(svc):
    write_job(svc.jobs, PJOB, kind="prd", prd_turns=[], conversation=[])
    assert card(svc, "prd", PJOB)[1]["why"] == "belum ada folder"
    write_job(svc.jobs, IJOB, kind="issue", conversation=[])
    assert card(svc, "prd", IJOB)[0] == 404 and card(svc, "prd", "j20261117_999999_ffff")[0] == 404 and card(svc, "prd", "../x")[0] == 404


# ---- the issue's examples -----------------------------------------------------------------------------------------------------

def issue_job(s, text, conv, **kw):
    sha = hashlib.sha256(text.encode()).hexdigest()
    d = write_job(s.jobs, IJOB, kind="issue", conversation=conv, issue_sha256=sha, **kw)
    (d / "issue.txt").write_text(text)
    return sha


def test_the_issue_examples_come_from_the_message_of_the_issue_and_not_from_the_last_turn(svc):
    text = issue_text(SAME, AFTER)
    sha = hashlib.sha256(text.encode()).hexdigest()
    conv = [{"from": "human", "text": "a"}, {"from": "writer", "text": "w1", "issue_sha256": sha, "examples": stored_for([SAME, AFTER]),
                                              "clashes": [], "questions": []},
            {"from": "human", "text": "b"}, {"from": "writer", "text": "only a reply", "clashes": [], "questions": []}]
    issue_job(svc, text, conv)
    got = svc.request("GET", f"/api/issues/{IJOB}")[1]["examples"]
    assert [(r["id"], r["status"]) for r in got["results"]] == [("e1", "pass"), ("e2", "unchecked")]


def test_an_issue_changed_after_the_turn_shows_no_status_and_an_old_message_is_marked(svc):
    text = issue_text(SAME)
    sha = hashlib.sha256(text.encode()).hexdigest()
    d = write_job(svc.jobs, IJOB, kind="issue", issue_sha256=sha, conversation=[
        {"from": "writer", "text": "w", "issue_sha256": sha, "examples": stored_for([SAME]), "clashes": [], "questions": []}])
    (d / "issue.txt").write_text(text + "\nEdited.\n")
    got = svc.request("GET", f"/api/issues/{IJOB}")[1]["examples"]
    assert got["results"] is None and got["why"] == "berkas tidak cocok dengan hasil"
    write_job(svc.jobs, IJOB, kind="issue", issue_sha256=sha, conversation=[
        {"from": "writer", "text": "w", "issue_sha256": sha, "clashes": [], "questions": []}])
    (d / "issue.txt").write_text(text)
    assert svc.request("GET", f"/api/issues/{IJOB}")[1]["examples"]["why"] == "dari sebelum gerbang contoh"
    assert svc.request("GET", "/api/issues/" + IJOB)[0] == 200


def test_an_issue_without_an_issue_yet_has_no_examples_card(svc):
    write_job(svc.jobs, IJOB, kind="issue", conversation=[{"from": "human", "text": "a"}])
    assert svc.request("GET", f"/api/issues/{IJOB}")[1]["examples"] is None


def handed_off(svc, text, audit=None, intake=None, **extra):
    sha = hashlib.sha256(text.encode()).hexdigest()
    parsed = eg.extract(text)[1]
    d = write_job(svc.jobs, IJOB, kind="issue", issue_sha256=sha, handoff={"job": CJOB1}, conversation=[
        {"from": "writer", "text": "w", "issue_sha256": sha, "examples": stored_for([SAME, AFTER]), "clashes": [], "questions": []}])
    (d / "issue.txt").write_text(text)
    c = code_job(svc, CJOB1, text)
    if intake is not None:
        (c / eg.INTAKE_FILE).write_text(json.dumps({"key": eg.intake_key("5" * 64, parsed), "results": intake, "skipped": None}))
    if audit is not None:
        (c / "examples_audit_a1.json").write_text(json.dumps({"key": eg.audit_key("7" * 64, parsed), "results": audit, "skipped": None, **extra}))
    return parsed


def test_after_a_handoff_the_card_has_the_intake_and_the_audit_of_the_code_job_and_a_failed_after_shows_fail(svc):
    text = issue_text(SAME, AFTER)
    handed_off(svc, text, intake=results_for([SAME, AFTER]),
               audit=[{"id": "e1", "tier": "same", "status": "pass", "actual": 4}, {"id": "e2", "tier": "after", "status": "fail", "actual": -4}])
    got = svc.request("GET", f"/api/issues/{IJOB}")[1]["examples"]
    assert got["at_base"]["kind"] == "results" and [r["where"] for r in got["at_base"]["results"]] == ["intake", "intake"]
    assert got["after_agent"]["kind"] == "results"
    assert [(r["id"], r["status"], r["where"]) for r in got["after_agent"]["results"]] == [("e1", "pass", "audit"), ("e2", "fail", "audit")]


@pytest.mark.parametrize("make, kind", [
    (None, "none"),
    (lambda c, parsed: (c / "examples_audit_a1.json").write_text(json.dumps({"key": "0" * 64, "results": []})), "stale"),
    (lambda c, parsed: (c / "examples_audit_a1.json").write_text(json.dumps({"key": eg.audit_key("7" * 64, parsed), "results": None,
                                                                              "reason": "the sandbox is not available"})), "pending"),
    (lambda c, parsed: (c / "examples_audit_a1.json").write_text("{not json"), "error"),
    (lambda c, parsed: (c / "examples_audit_a1.json").write_text(json.dumps({"key": eg.audit_key("7" * 64, parsed), "results": [
        {"id": "e1", "tier": "same", "status": "great"}]})), "error"),
])
def test_an_audit_that_is_missing_stale_pending_or_damaged_is_said_so_and_never_a_pass(svc, make, kind):
    text = issue_text(SAME, AFTER)
    parsed = handed_off(svc, text)
    if make:
        make(svc.jobs / CJOB1, parsed)
    got = svc.request("GET", f"/api/issues/{IJOB}")[1]["examples"]["after_agent"]
    assert got["kind"] == kind and got["results"] is None


# ---- queues -------------------------------------------------------------------------------------------------------------------

def test_a_queue_card_follows_the_jobs_without_git_and_without_a_process(svc, monkeypatch):
    t1, t2 = issue_text(SAME, title="One"), issue_text(AFTER, title="Two")
    d, texts = write_queue(svc, [(t1, CJOB1), (t2, None)], approved={"sha": "x", "at": "t", "by": "u"})
    c1 = code_job(svc, CJOB1, t1, state="APPLIED", log=[{"at": "t", "what": "state", "old": "REVIEW_READY", "new": "APPLIED",
                                                         "commit": "e" * 40, "as_is": True}])
    j = json.loads((c1 / "job.json").read_text())
    j["inputs"]["commit"] = "c" * 40
    (c1 / "job.json").write_text(json.dumps(j))
    for name in ("run", "Popen", "check_output"):
        monkeypatch.setattr(subprocess, name, lambda *a, **k: (_ for _ in ()).throw(AssertionError("a process was started")))
    monkeypatch.setattr(os, "fork", lambda: (_ for _ in ()).throw(AssertionError("a fork")))
    status, c = card(svc, "queue", QID)
    assert status == 200 and c["state"] == "WAITING" and "HEAD tidak diperiksa dari chat" in c["next"]
    first, second = c["items"]
    assert (first["n"], first["job_state"], first["applied"], first["text_matches"]) == (1, "APPLIED", "e" * 12, True)
    assert second["job"] is None and [(r["id"], r["status"]) for r in second["examples"]["results"]] == [("e2", rcards.NOT_RUN)]
    assert "argus " not in json.dumps(c)                                                       # no CLI line of `derive` is shown


def test_a_queue_state_pending_closed_and_stopped(svc):
    t1 = issue_text(SAME)
    write_queue(svc, [(t1, None)])
    assert card(svc, "queue", QID)[1]["state"] == "PENDING"
    write_queue(svc, [(t1, None)], closed={"note": "stuck", "at": "t"})
    c = card(svc, "queue", QID)[1]
    assert c["state"] == "CLOSED" and c["closed"] == "stuck"
    write_queue(svc, [(t1, CJOB1)], approved={"sha": "x"})
    code_job(svc, CJOB1, t1, state="AGENT_FAILED")
    c = card(svc, "queue", QID)[1]
    assert c["state"] == "STOPPED" and "AGENT_FAILED" in c["next"]


def test_an_issue_file_of_the_queue_that_changed_shows_no_calls_and_text_matches_false(svc):
    t1 = issue_text(SAME)
    d, _ = write_queue(svc, [(t1, None)], approved={"sha": "x"})
    (d / "issue-1.md").write_text(t1 + "\nedited\n")
    item = card(svc, "queue", QID)[1]["items"][0]
    assert item["text_matches"] is False and item["title"] == "" and item["examples"]["calls"] == [] and item["examples"]["why"] == "berkas berubah"


def test_a_queue_of_another_jobs_directory_is_listed_without_its_items_and_not_opened(svc, tmp_path):
    write_queue(svc, [(issue_text(SAME), CJOB1)], approved={"sha": "x"}, jobs_dir=str(tmp_path / "elsewhere"))
    c = card(svc, "queue", QID)[1]
    assert c["jobs_dir_ok"] is False and c["items"] is None and c["why"] == "jobs dir lain"
    row = [r for r in svc.request("GET", "/api/cards")[1]["rows"] if r["id"] == QID][0]
    assert row["items"] is None and row["why"] == "jobs dir lain"


def test_a_queue_that_is_a_symlink_too_big_or_misshapen_is_a_404(svc, tmp_path):
    (svc.queues / "real").mkdir()
    os.symlink(tmp_path / "queues" / "real", svc.queues / QID)
    assert card(svc, "queue", QID)[0] == 404
    os.unlink(svc.queues / QID)
    d, _ = write_queue(svc, [(issue_text(SAME), None)], approved={"sha": "x"})
    (d / "queue.json").write_text(json.dumps({"id": QID, "pad": "x" * (rcards.QUEUE_MAX + 10)}))
    assert card(svc, "queue", QID)[0] == 404
    (d / "queue.json").write_text(json.dumps({"id": QID, "items": []}))
    assert card(svc, "queue", QID)[0] == 404
    assert card(svc, "queue", "q1")[0] == 404 and card(svc, "queue", "..")[0] == 404 and card(svc, "queue", PJOB)[0] == 404


def test_a_queue_remembers_the_prd_job_it_came_from_without_opening_the_folder(svc):
    write_prd(svc.jobs, [issue_text(SAME)], [stored_for([SAME])])
    write_queue(svc, [(issue_text(SAME), None)], approved={"sha": "x"}, prd={"sha": "a" * 64, "dir": str(svc.jobs / PJOB / "prd-w1")})
    assert card(svc, "prd", PJOB)[1]["queues"] == [QID]


# ---- the list, safety -----------------------------------------------------------------------------------------------------

def test_the_list_has_prd_jobs_and_queues_newest_first_and_no_issue_or_code_jobs(svc):
    write_prd(svc.jobs, [issue_text(SAME)], [stored_for([SAME])])
    write_job(svc.jobs, IJOB, kind="issue", conversation=[])
    write_job(svc.jobs, CJOB1, kind="code")
    write_queue(svc, [(issue_text(SAME), None)], approved={"sha": "x"})
    got = svc.request("GET", "/api/cards")[1]
    assert [(r["kind"], r["id"]) for r in got["rows"]] == [("queue", QID), ("prd", PJOB)] and got["truncated"] is False
    prd_row = got["rows"][1]
    assert prd_row["title"] == "bikin dua perubahan" and prd_row["items"] == 1 and "prd_job" not in got["rows"][0]


def test_the_list_is_cut_at_the_scan_cap(svc, monkeypatch):
    monkeypatch.setattr(rcards, "SCAN_JOBS", 3)
    for i in range(5):
        write_job(svc.jobs, f"j20261117_10000{i}_aaaa", kind="prd", prd_turns=[], conversation=[])
    got = svc.request("GET", "/api/cards")[1]
    assert len(got["rows"]) == 3 and got["truncated"] is True


def test_a_key_in_a_call_withholds_the_examples_of_the_card_and_not_the_rest(svc):
    leaky = {**SAME, "setup": "from src.shop import total  # sk-ant-" + "a" * 30}
    write_prd(svc.jobs, [issue_text(leaky)], [stored_for([leaky])])
    c = card(svc, "prd", PJOB)[1]
    assert c["items"][0]["examples"] in ({"withheld": True},) or "sk-ant" not in json.dumps(c)
    assert "sk-ant-" + "a" * 30 not in json.dumps(c) and c["items"][0]["title"]


def test_a_value_that_is_not_text_is_written_as_one_scrubbed_string(svc):
    nested = {**SAME, "expect": {"b": [1, 2], "a": "x‮y"}}
    write_prd(svc.jobs, [issue_text(nested)], [stored_for([nested])])
    call = card(svc, "prd", PJOB)[1]["items"][0]["examples"]["calls"][0]
    assert isinstance(call["expect"], str) and "‮" not in call["expect"] and call["expect"].startswith('{"a"')


def test_a_fifo_as_job_json_does_not_block_the_server(svc):
    d = svc.jobs / PJOB
    d.mkdir()
    os.mkfifo(d / "job.json")
    out = []
    t = threading.Thread(target=lambda: out.append(svc.request("GET", f"/api/cards/prd/{PJOB}")[0]), daemon=True)
    t.start()
    t.join(10)
    assert out == [404] and svc.request("GET", "/api/cards")[0] == 200


def test_a_symlinked_job_directory_is_never_read(svc, tmp_path):
    real = tmp_path / "elsewhere" / PJOB
    write_job(tmp_path / "elsewhere", PJOB, kind="prd", prd_turns=[], conversation=[])
    os.symlink(real, svc.jobs / PJOB)
    assert card(svc, "prd", PJOB)[0] == 404 and svc.request("GET", "/api/cards")[1]["rows"] == []


def test_the_routes_are_get_only_host_checked_and_write_nothing(svc, tmp_path):
    write_prd(svc.jobs, [issue_text(SAME)], [stored_for([SAME])])
    write_queue(svc, [(issue_text(SAME), None)], approved={"sha": "x"})
    before = sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*"))
    for path in ("/api/cards", f"/api/cards/prd/{PJOB}", f"/api/cards/queue/{QID}"):
        assert svc.request("GET", path)[0] == 200
        assert svc.request("GET", path, host="evil.example:8712")[0] in (400, 403, 421)
        for method in ("POST", "PUT", "DELETE", "PATCH"):
            assert svc.request(method, path)[0] in (404, 405)
    assert sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*")) == before and svc.spawner.calls == []


def test_a_reading_that_is_not_a_file_of_the_chat_is_not_there_without_actions(tmp_path):
    from router import chat as rc
    chat = rc.Chat(tmp_path)                                                 # no actions: a read-only chat has no card routes
    assert chat.actions is None


# ---- the page and the issue page ----------------------------------------------------------------------------------------------

def test_the_issue_page_shows_the_issue_without_its_block_when_the_examples_card_is_there(svc):
    text = issue_text(SAME)
    sha = hashlib.sha256(text.encode()).hexdigest()
    d = write_job(svc.jobs, IJOB, kind="issue", issue_sha256=sha, conversation=[
        {"from": "writer", "text": "w", "issue_sha256": sha, "examples": stored_for([SAME]), "clashes": [], "questions": []}])
    (d / "issue.txt").write_text(text)
    got = svc.request("GET", f"/api/issues/{IJOB}")[1]
    assert "argus-examples" not in got["issue"]["text"] and got["examples"]["calls"][0]["says"].startswith("Two prices")
    assert got["issue"]["sha12"] == sha[:12]                                    # the sha is still the whole file's


def test_the_cards_part_of_the_page_only_reads_and_only_writes_text():
    js = (Path(__file__).resolve().parent.parent / "router" / "chat_static" / "app.js").read_text()
    part = js[js.index("// ---- T2: read-only cards"):js.index("  function setMode(m) {")]
    for banned in ("post(", "innerHTML", "outerHTML", "insertAdjacentHTML", "localStorage", "sessionStorage", "document.cookie", "fetch(",
                   "XMLHttpRequest", "method:", "eval(", "new Function", "document.write"):
        assert banned not in part, banned
    assert part.count('get("/api/cards') == 2 and "ditulis model" in part and "kode itu ditulis model dan bisa memalsukannya" in part
    html = (Path(__file__).resolve().parent.parent / "router" / "chat_static" / "index.html").read_text()
    assert 'data-mode="cards"' in html


# ---- the review of the T2 code (Opus) -------------------------------------------------------------------------------------------

def test_no_card_or_row_carries_the_repository_path(svc):
    write_prd(svc.jobs, [issue_text(SAME)], [stored_for([SAME])])
    write_queue(svc, [(issue_text(SAME), None)], approved={"sha": "x"})
    for path in ("/api/cards", f"/api/cards/prd/{PJOB}", f"/api/cards/queue/{QID}"):
        assert "/secret/path" not in json.dumps(svc.request("GET", path)[1]), path


def test_the_queue_money_is_counted_from_the_jobs_and_stops_the_queue_like_derive(svc):
    t1, t2, t3 = issue_text(SAME, title="1"), issue_text(AFTER, title="2"), issue_text(SAME, title="3")
    write_queue(svc, [(t1, CJOB1), (t2, CJOB2), (t3, None)], approved={"sha": "x"}, max_usd=1.0, job_cap_usd=0.5)
    for jid, t, commit in ((CJOB1, t1, "c" * 40), (CJOB2, t2, "e" * 40)):
        d = code_job(svc, jid, t, state="APPLIED", log=[{"at": "t", "what": "state", "new": "APPLIED", "commit": "e" * 40 if jid == CJOB1 else "f" * 40,
                                                         "as_is": True}])
        j = json.loads((d / "job.json").read_text())
        j["inputs"]["commit"] = commit
        j["max_usd"] = 0.5
        (d / "job.json").write_text(json.dumps(j))
    c = card(svc, "queue", QID)[1]
    assert c["state"] == "STOPPED" and "uang antrean" in c["next"]


def test_an_item_job_that_is_there_but_not_a_code_job_stops_the_queue_and_a_missing_one_waits(svc):
    t1 = issue_text(SAME)
    write_queue(svc, [(t1, CJOB1)], approved={"sha": "x"})
    assert card(svc, "queue", QID)[1]["state"] == "WAITING"                                # the recorded job is not there: start again
    write_job(svc.jobs, CJOB1, kind="issue")
    c = card(svc, "queue", QID)[1]
    assert c["state"] == "STOPPED" and "bukan job code" in c["next"]
    (svc.jobs / CJOB1 / "job.json").write_text("{" + "x" * 10)
    assert card(svc, "queue", QID)[1]["state"] == "STOPPED"


def test_a_jobs_directory_that_is_a_link_is_still_read(tmp_path):
    real = tmp_path / "real_jobs"
    real.mkdir()
    s = Service(tmp_path)
    try:
        s.stop()
    except Exception:
        pass
    os.symlink(real, tmp_path / "linked")
    c = rcards.Cards(tmp_path / "linked", tmp_path / "queues", lambda x: x)
    write_job(real, PJOB, kind="prd", prd_turns=[], conversation=[])
    assert c.prd(PJOB)["why"] == "belum ada folder"


def test_the_statuses_of_a_job_bound_to_another_commit_are_not_shown_on_the_item(svc):
    t1 = issue_text(SAME, AFTER)
    write_queue(svc, [(t1, CJOB1)], approved={"sha": "x"})
    d = code_job(svc, CJOB1, t1, state="REVIEW_READY")
    j = json.loads((d / "job.json").read_text())
    j["inputs"]["commit"] = "9" * 40                                                          # another base than the queue's
    (d / "job.json").write_text(json.dumps(j))
    parsed = eg.extract(t1)[1]
    (d / eg.INTAKE_FILE).write_text(json.dumps({"key": eg.intake_key("5" * 64, parsed), "results": results_for([SAME, AFTER]), "skipped": None}))
    c = card(svc, "queue", QID)[1]
    assert c["state"] == "STOPPED" and c["items"][0]["examples"]["at_base"] is None and c["items"][0]["examples"]["after_agent"] is None


def test_a_key_split_between_setup_and_run_withholds_the_examples(svc):
    # a key cut in two by the fields (the text of setup ends where the text of run goes on); a key built by code (K + "...") cannot be seen
    split = {**SAME, "setup": "from src.shop import total  # sk-ant-", "run": "api03abcdefghij and total([2, 3], 1)"}
    write_prd(svc.jobs, [issue_text(split)], [stored_for([split])])
    c = card(svc, "prd", PJOB)[1]
    assert c["items"][0]["examples"] == {"withheld": True}
    text = issue_text(split)
    sha = hashlib.sha256(text.encode()).hexdigest()
    d = write_job(svc.jobs, IJOB, kind="issue", issue_sha256=sha, conversation=[
        {"from": "writer", "text": "w", "issue_sha256": sha, "examples": stored_for([split]), "clashes": [], "questions": []}])
    (d / "issue.txt").write_text(text)
    assert svc.request("GET", f"/api/issues/{IJOB}")[1]["examples"] == {"withheld": True}


def test_a_card_that_cannot_be_built_is_a_404_and_the_issue_page_still_loads(svc):
    text = issue_text(SAME)
    sha = hashlib.sha256(text.encode()).hexdigest()
    d = write_job(svc.jobs, IJOB, kind="issue", issue_sha256=sha, handoff={"job": CJOB1}, conversation=[
        {"from": "writer", "text": "w", "issue_sha256": sha, "examples": {"examples": [SAME], "results": [1], "tier_moves": 5}, "clashes": [], "questions": []}])
    (d / "issue.txt").write_text(text)
    write_job(svc.jobs, CJOB1, kind="code", intake="a string", stages=[1, 2])
    status, got = svc.request("GET", f"/api/issues/{IJOB}")
    assert status == 200 and got["id"] == IJOB
    write_job(svc.jobs, PJOB, kind="prd", prd_turns=[{"turn": "w1", "items": "x", "folder_sha": 5}], stages=[1], conversation=None)
    assert card(svc, "prd", PJOB)[0] in (200, 404) and svc.request("GET", "/api/cards")[0] == 200
    write_queue(svc, [(text, None)], approved={"sha": "x"}, closed=True)
    assert card(svc, "queue", QID)[0] in (200, 404) and svc.request("GET", "/api/cards")[0] == 200


def test_the_money_spent_is_unknown_not_zero_when_a_stage_has_no_number(svc):
    d, _ = write_prd(svc.jobs, [issue_text(SAME)], [stored_for([SAME])])
    j = json.loads((d / "job.json").read_text())
    j["stages"]["w2"] = {"kind": "write", "run_id": "x"}
    (d / "job.json").write_text(json.dumps(j))
    assert card(svc, "prd", PJOB)[1]["money"]["spent"] is None


def test_results_for_only_some_of_the_calls_or_for_another_tier_are_not_shown(svc):
    one = stored_for([SAME, AFTER])
    one["results"] = one["results"][:1]
    write_prd(svc.jobs, [issue_text(SAME, AFTER)], [one])
    assert card(svc, "prd", PJOB)[1]["items"][0]["examples"]["results"] is None
    other = stored_for([SAME, AFTER])
    other["results"][0]["tier"] = "whatif"
    write_prd(svc.jobs, [issue_text(SAME, AFTER)], [other])
    assert card(svc, "prd", PJOB)[1]["items"][0]["examples"]["results"] is None




def test_a_stored_result_file_that_is_not_utf8_is_an_error_not_a_result(svc):
    text = issue_text(SAME, AFTER)
    parsed = handed_off(svc, text)
    raw = json.dumps({"key": eg.audit_key("7" * 64, parsed), "results": results_for([SAME, AFTER]), "skipped": None}).encode()
    (svc.jobs / CJOB1 / "examples_audit_a1.json").write_bytes(raw + b"\xff\xfe")
    assert svc.request("GET", f"/api/issues/{IJOB}")[1]["examples"]["after_agent"]["kind"] == "error"


def test_the_issue_page_keeps_the_block_when_no_example_can_be_shown(svc):
    text = ISSUE.replace("Environment: pyenv", "```argus-examples json\n[]\n```\n\nEnvironment: pyenv")       # a block that does not parse
    sha = hashlib.sha256(text.encode()).hexdigest()
    d = write_job(svc.jobs, IJOB, kind="issue", issue_sha256=sha, conversation=[
        {"from": "writer", "text": "w", "issue_sha256": sha, "examples": stored_for([SAME]), "clashes": [], "questions": []}])
    (d / "issue.txt").write_text(text)
    assert "argus-examples" in svc.request("GET", f"/api/issues/{IJOB}")[1]["issue"]["text"]


def test_the_page_marks_a_stale_folder_item_by_item_and_a_failed_card_has_a_way_back():
    js = (Path(__file__).resolve().parent.parent / "router" / "chat_static" / "app.js").read_text()
    part = js[js.index("// ---- T2: read-only cards"):js.index("  function setMode(m) {")]
    assert "itemCard(it, d.stale || d.superseded)" in part and 'if (seq !== cardSeq || mode !== "cards") { return; }' in part
    assert part.count('"Semua kartu"') == 2 and 'r.status === "pass"' in part
