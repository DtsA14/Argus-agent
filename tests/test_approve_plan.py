"""SPEC_KARTU_SETUJU PR 2 (T3): the plan card, GET /api/approve/prd/<job> (router/approve_cards.py): block A (the request as the human wrote it,
the writer's reply marked as model text, the number of issues, the cost) and block B (the examples as numbers, in the fixed order same,
whatif, after, with the machine's proof words). Read only. Real files in a temporary jobs directory, a real server on a free port; no model,
no Docker, no process."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_chat_cards import (AFTER, PJOB, SAME, issue_text, stored_for, svc, write_job, write_prd)  # noqa: E402,F401

from router import approve_cards as ac  # noqa: E402

SHOP = "def total(prices, discount):\n    return 0\n"
WHATIF = {"id": "e3", "tier": "whatif", "says": "With a floor of 5 a total of 2 is 5", "setup": "import src.shop as shop",
          "run": "shop.total([2], 0)", "expect": 5, "overrides": {"src.shop.FLOOR": 5}}


def plan(s, job=PJOB):
    return s.request("GET", f"/api/approve/prd/{job}")


def with_tree(d, source=SHOP):
    root = d / "runs" / f"{PJOB}-w1" / "source" / "src"
    root.mkdir(parents=True, exist_ok=True)
    (root / "__init__.py").write_text("")
    (root / "shop.py").write_text(source)


def one(s, examples, stored=None, **kw):
    text = issue_text(*examples)
    d, files = write_prd(s.jobs, [text], [stored if stored is not None else stored_for(examples)], **kw)
    with_tree(d)
    return d


def ex_by_id(c, eid, item=0):
    return next(e for e in c["items"][item]["examples"] if e["id"] == eid)


# ---- block B: the examples as numbers -----------------------------------------------------------------------------------------

def test_the_examples_are_shown_as_numbers_in_the_fixed_order_with_names_from_the_frozen_tree(svc):
    one(svc, [AFTER, WHATIF, SAME])                                  # written in the wrong order on purpose
    status, c = plan(svc)
    assert status == 200 and c["kind"] == "plan" and c["id"] == PJOB
    item = c["items"][0]
    assert [e["tier"] for e in item["examples"]] == ["same", "whatif", "after"]
    e1 = ex_by_id(c, "e1")
    assert e1["showable"] is True and e1["call"] == "src.shop.total"
    assert [(i["name"], i["name_source"], i["shown"]) for i in e1["inputs"]] == [
        ("prices", "def", "[\n  2\n  3\n]"), ("discount", "def", "1")]
    assert e1["output"][0]["shown"] == "4" and e1["says"].startswith("Two prices")
    e3 = ex_by_id(c, "e3")
    assert e3["assumptions"] == [{"name": "src.shop.FLOOR", "value_json": "5", "shown": "5"}]
    assert item["counts"] == {"calls": 3, "same": 1, "whatif": 1, "after": 1}


def test_the_proof_words_at_the_base_never_say_it_matches(svc):
    one(svc, [SAME, AFTER, WHATIF], stored=stored_for([SAME, AFTER, WHATIF]))
    c = plan(svc)[1]
    e1, e2, e3 = ex_by_id(c, "e1"), ex_by_id(c, "e2"), ex_by_id(c, "e3")
    assert e1["proof"]["wording"] == "kode sekarang memberi angka ini: 4" and e1["proof"]["kind"] == "dasar" and e1["proof"]["status"] == "pass"
    assert e2["proof"]["wording"] == "belum ada (memang belum dibuat); kode sekarang memberi -4"
    assert e3["proof"]["wording"].startswith("kode sekarang memberi angka ini: 5")
    for e in (e1, e2, e3):
        assert "cocok" not in e["proof"]["wording"].lower() and "benar" not in e["proof"]["wording"].lower()
    assert e1["proof"]["actual_json"] == "4"


def test_an_after_example_without_a_base_value_and_a_failed_status_are_worded_without_a_match_word(svc):
    stored = stored_for([SAME, AFTER], e1="fail")
    stored["results"][1].pop("base_actual")
    one(svc, [SAME, AFTER], stored=stored)
    c = plan(svc)[1]
    assert ex_by_id(c, "e2")["proof"]["wording"] == "belum ada (memang belum dibuat)"
    w = ex_by_id(c, "e1")["proof"]["wording"]
    assert w.startswith("kode sekarang memberi angka ini: 4") and "gerbang menandai: fail" in w and "cocok" not in w.lower()


def test_no_proof_is_claimed_when_the_status_is_not_for_these_files(svc):
    d = one(svc, [SAME])
    (d / "prd-w1" / "issue-1.md").write_text(issue_text({**SAME, "expect": 5}))
    c = plan(svc)[1]
    e = c["items"][0]["examples"]
    assert all(x["proof"]["status"] is None and "belum diperiksa mesin" in x["proof"]["wording"] for x in e) or e == []
    assert c["why"] is None or isinstance(c["why"], str)


def test_an_item_the_writer_did_not_run_has_no_proof_yet(svc):
    t1, t2 = issue_text(SAME), issue_text(AFTER, title="Second")
    d, _ = write_prd(svc.jobs, [t1, t2], [stored_for([SAME]), {"examples": [AFTER], "results": [], "no_examples": None, "note": None, "tier_moves": []}])
    with_tree(d)
    c = plan(svc)[1]
    p = c["items"][1]["examples"][0]["proof"]
    assert p["status"] is None and "dijalankan saat job code item ini mulai" in p["wording"]


def test_a_warning_when_an_issue_has_no_example_for_the_new_behaviour(svc):
    one(svc, [SAME])
    item = plan(svc)[1]["items"][0]
    assert item["warning"] == ac.NO_NEW_WARNING and "tidak diperiksa mesin" in item["warning"]
    assert item["counts"]["after"] == 0
    one(svc, [SAME, AFTER])
    assert plan(svc)[1]["items"][0]["warning"] is None
    one(svc, [SAME, WHATIF])
    assert plan(svc)[1]["items"][0]["warning"] is None


def test_an_issue_with_no_examples_shows_the_writers_reason_as_model_text_and_the_warning(svc):
    stored = {"examples": [], "results": [], "no_examples": "the text is the contract", "note": None, "tier_moves": []}
    d, _ = write_prd(svc.jobs, [issue_text()], [stored])
    with_tree(d)
    item = plan(svc)[1]["items"][0]
    assert item["examples"] == [] and item["warning"] == ac.NO_NEW_WARNING
    assert item["no_examples"] == "the text is the contract" and item["counts"]["calls"] == 0


def test_an_example_outside_the_grammar_says_so_and_is_counted_as_a_defect(svc):
    odd = {**SAME, "setup": "from src.shop import total\nFLOOR = 9", "id": "e1"}
    one(svc, [odd, AFTER])
    c = plan(svc)[1]
    e = ex_by_id(c, "e1")
    assert e["showable"] is False and "tidak bisa ditampilkan" in e["why"] and e["inputs"] == [] and e["output"] is None
    assert c["items"][0]["defects"] == 1 and c["defects"] == 1


def test_positional_names_that_the_tree_cannot_give_are_a_defect_not_a_guess(svc):
    d = one(svc, [SAME])
    import shutil
    shutil.rmtree(d / "runs")
    c = plan(svc)[1]
    e = ex_by_id(c, "e1")
    assert e["showable"] is False and [i["name"] for i in e["inputs"]] == ["argumen 1", "argumen 2"] and c["defects"] == 1


def test_the_fixed_line_is_always_there_and_says_what_the_machine_does_not_check(svc):
    one(svc, [SAME, AFTER])
    c = plan(svc)[1]
    assert c["fixed_line"] == ac.FIXED_LINE
    for part in ("Mesin memeriksa", "Tidak diperiksa mesin", "aturan bisnis", "pembaca patch", "angka di teks issue"):
        assert part in c["fixed_line"]
    assert "aman" not in json.dumps(c, ensure_ascii=False).lower().replace("amankan", "")


# ---- block A: the request, the reply, the cost --------------------------------------------------------------------------------

def test_the_request_is_the_first_human_message_word_for_word_and_the_reply_is_marked_as_model_text(svc):
    one(svc, [SAME, AFTER])
    c = plan(svc)[1]
    assert c["request"] == "bikin dua perubahan\nlagi" and c["request_truncated"] is False
    assert c["summary"] == "ok" and c["summary_by"] == "model"
    assert c["issue_count"] == 1


def test_who_wrote_the_request_is_only_claimed_when_the_job_says_it(svc):
    d = one(svc, [SAME, AFTER])
    assert plan(svc)[1]["request_by"] == "tidak_tercatat"
    data = json.loads((d / "job.json").read_text())
    data["log"] = [{"what": "created", "by": "ubuntu", "via": "ui"}]
    (d / "job.json").write_text(json.dumps(data))
    assert plan(svc)[1]["request_by"] == "chat"


def test_a_very_long_request_is_cut_and_says_so(svc):
    d = one(svc, [SAME, AFTER])
    data = json.loads((d / "job.json").read_text())
    data["conversation"][0]["text"] = "x" * 9000
    (d / "job.json").write_text(json.dumps(data))
    c = plan(svc)[1]
    assert c["request_truncated"] is True and len(c["request"]) <= ac.REQUEST_MAX


def test_the_cost_is_spent_proposed_and_a_reference_from_earlier_applied_code_jobs(svc):
    one(svc, [SAME, AFTER])
    c = plan(svc)[1]
    assert c["cost"]["spent"] == 0.05 and c["cost"]["proposed"] == 2.0 and c["cost"]["reference"] is None
    for n, usd in enumerate((0.10, 0.30, 0.20, 0.50), 1):
        write_job(svc.jobs, f"j20261116_10000{n}_aaa{n}", kind="code", state="APPLIED", stages={"a1": {"kind": "agent", "usd": usd}})
    write_job(svc.jobs, "j20261116_100009_aaa9", kind="code", state="BLOCKED", stages={"a1": {"kind": "agent", "usd": 9.0}})
    write_job(svc.jobs, "j20261116_100008_aaa8", kind="code", state="APPLIED", stages={"a1": {"kind": "agent"}})      # unknown cost: left out
    ref = plan(svc)[1]["cost"]["reference"]
    assert ref == {"median": 0.25, "n": 4, "of": "job code yang sudah di-apply"}


# ---- state, binding, leaks, safety ---------------------------------------------------------------------------------------------

def test_stale_and_superseded_are_reported(svc):
    d = one(svc, [SAME, AFTER])
    data = json.loads((d / "job.json").read_text())
    data["inputs"]["commit"] = "d" * 40
    (d / "job.json").write_text(json.dumps(data))
    (d / "prd-w1" / "SUPERSEDED").write_text("x")
    c = plan(svc)[1]
    assert c["stale"] is True and c["superseded"] is True


def test_not_a_prd_job_or_a_bad_id_or_a_missing_job_is_404(svc):
    one(svc, [SAME])
    write_job(svc.jobs, "j20261117_100100_bbbb", kind="code")
    for job in ("j20261117_100100_bbbb", "j20261117_199999_ffff", "..%2Fx", "nope", PJOB + "x"):
        assert plan(svc, job)[0] == 404
    assert svc.request("POST", f"/api/approve/prd/{PJOB}")[0] in (404, 405)


def test_the_route_checks_host_and_fetch_site_like_the_other_reads(svc):
    one(svc, [SAME])
    assert svc.request("GET", f"/api/approve/prd/{PJOB}", host="evil.example")[0] == 421
    assert svc.request("GET", f"/api/approve/prd/{PJOB}", headers={"Sec-Fetch-Site": "cross-site"})[0] == 403
    assert svc.request("GET", f"/api/approve/prd/{PJOB}", headers={"Sec-Fetch-Site": "same-origin"})[0] == 200


def test_a_key_pattern_in_an_example_never_reaches_the_card(svc):
    leak = {**SAME, "run": "total(['sk-or-v1-" + "a" * 40 + "'], 0)"}
    one(svc, [leak, AFTER])
    status, c = plan(svc)
    assert status == 200 and "sk-or-v1" not in json.dumps(c)


def test_text_is_scrubbed(svc):
    d = one(svc, [SAME, AFTER])
    data = json.loads((d / "job.json").read_text())
    data["conversation"][0]["text"] = "hi‮ there\x00"
    data["conversation"][1]["text"] = "ok‮"
    (d / "job.json").write_text(json.dumps(data))
    c = plan(svc)[1]
    assert "‮" not in json.dumps(c, ensure_ascii=False) and "\x00" not in json.dumps(c)


def test_the_repository_path_is_never_in_the_card(svc):
    one(svc, [SAME, AFTER])
    assert "/secret/path" not in json.dumps(plan(svc)[1])


def test_the_card_writes_nothing_and_starts_nothing(svc, monkeypatch, tmp_path):
    one(svc, [SAME, AFTER, WHATIF])
    for name in ("Popen", "run", "call", "check_output", "check_call"):
        monkeypatch.setattr(subprocess, name, lambda *a, **k: (_ for _ in ()).throw(AssertionError("a process was started")))
    monkeypatch.setattr(os, "fork", lambda: (_ for _ in ()).throw(AssertionError("a fork")))

    def snap():
        return sorted((str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in svc.jobs.rglob("*"))
    before = snap()
    assert plan(svc)[0] == 200
    assert snap() == before


def test_the_module_is_read_only_text():
    import re
    text = Path(ac.__file__).read_text()
    for banned in ("subprocess", "socket", "urllib", "os.system", "os.write", "os.remove", "os.rename", "O_WRONLY", "O_RDWR", "O_CREAT", "write_text",
                   "write_bytes", "shutil", "harness.llm", "from models"):
        assert banned not in text, banned
    assert not re.search(r"(?<![\w.])(exec|eval|compile|open)\(", text)


def test_the_listing_of_the_other_cards_is_unchanged_and_the_t2_card_still_answers(svc):
    one(svc, [SAME, AFTER])
    assert svc.request("GET", f"/api/cards/prd/{PJOB}")[0] == 200
    assert svc.request("GET", "/api/cards")[0] == 200


def test_the_page_has_a_plan_view_reached_from_the_prd_card_and_writes_only_text():
    js = (Path(__file__).resolve().parent.parent / "router" / "chat_static" / "app.js").read_text()
    assert 'get("/api/approve/prd/" + encodeURIComponent(id))' in js
    assert 'plan.addEventListener("click", function () { showPlan(id); });' in js and '"Kartu rencana (angka)"' in js
    for title in ("Yang tidak boleh berubah", "Kalau ... maka", "Yang berubah"):
        assert title in js
    part = js[js.index("function planExample"):js.index("// ---- T2: read-only cards")]
    assert "innerHTML" not in part and "insertAdjacentHTML" not in part and "document.write" not in part
    assert 'modelLine(d, e.says)' in part and "e.proof.wording" in part and "it.warning" in part
    assert part.count('"Semua kartu"') == 2


def test_the_chat_serves_the_pinned_files():
    import hashlib
    from router import chat as rc
    for name, sha in rc.STATIC_SHA256.items():
        assert hashlib.sha256((rc.STATIC_DIR / name).read_bytes()).hexdigest() == sha
