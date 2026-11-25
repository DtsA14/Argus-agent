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
from router.cards import NOT_RUN_WHY  # noqa: E402

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
    bind_reply(d)
    return d


def bind_reply(d, text="ok", stage="w1"):
    data = json.loads((d / "job.json").read_text())
    data["conversation"][1].update(text=text, stage=stage, folder_sha=data["prd_turns"][-1]["folder_sha"])
    (d / "job.json").write_text(json.dumps(data))


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


def no_proof(c):
    ex_ = c["items"][0]["examples"]
    assert ex_ and all(x["proof"]["status"] is None and "belum diperiksa mesin" in x["proof"]["wording"] for x in ex_)
    assert all(x["proof"]["actual_json"] is None for x in ex_)


def test_no_proof_when_only_the_prd_file_changed_so_the_folder_sha_differs(svc):
    d = one(svc, [SAME])
    assert plan(svc)[1]["items"][0]["examples"][0]["proof"]["status"] == "pass"
    (d / "prd-w1" / "PRD.md").write_text("Goal: changed.\n")
    no_proof(plan(svc)[1])


def test_no_proof_when_only_the_stored_examples_changed_so_the_digest_differs(svc):
    d = one(svc, [SAME])
    data = json.loads((d / "job.json").read_text())
    data["prd_turns"][-1]["examples"][0]["examples"][0]["expect"] = 5
    (d / "job.json").write_text(json.dumps(data))
    no_proof(plan(svc)[1])


def test_no_proof_when_the_issue_file_changed(svc):
    d = one(svc, [SAME])
    (d / "prd-w1" / "issue-1.md").write_text(issue_text({**SAME, "expect": 5}))
    no_proof(plan(svc)[1])


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
    assert item["examples"] == [] and item["warning"] == ac.NO_NEW_WARNING and item["why"] is None
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


def test_the_fixed_line_is_always_there_and_says_who_checks_what(svc):
    one(svc, [SAME, AFTER])
    c = plan(svc)[1]
    assert c["fixed_line"] == ac.FIXED_LINE
    for part in ("Mesin memeriksa: kode memberi angka ini", "Dibaca Claude, bukan mesin dan bukan Anda: apakah angkanya sesuai permintaan",
                 "Tidak diperiksa siapa pun: aturan bisnis yang tidak tertulis", "pembaca patch: Claude", "angka di teks issue"):
        assert part in c["fixed_line"]
    assert "(Anda)" not in c["fixed_line"] and "tugas Atha" not in c["fixed_line"]
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
    assert ref == {"median": 0.25, "n": 4, "of": "job code yang sudah di-apply", "cap_median": 1.0, "cap_n": 5}


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
    assert 'say(d, "model", MODEL, e.says)' in part and "e.proof.wording" in part and "it.warning" in part
    assert part.count('"All cards"') == 1 and part.count("cardButtons(") == 5                 # one definition, two cards, each with its failure path


def test_the_chat_serves_the_pinned_files():
    import hashlib
    from router import chat as rc
    for name, sha in rc.STATIC_SHA256.items():
        assert hashlib.sha256((rc.STATIC_DIR / name).read_bytes()).hexdigest() == sha


# ---- the fixes of the review ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_a_non_finite_value_is_shown_as_what_it_is_never_as_none(bad):
    for tier, key in (("same", "actual"), ("after", "base_actual")):
        p = ac.Approve._proof(tier, {"status": "pass", key: bad}, None)
        assert "None" not in p["wording"] and ("nan" in p["wording"] or "inf" in p["wording"])


def test_the_summary_is_the_reply_of_this_folder_not_the_last_message(svc):
    d = one(svc, [SAME, AFTER])
    data = json.loads((d / "job.json").read_text())
    data["conversation"].append({"from": "writer", "text": "a later reply about something else", "stage": "w2", "folder_sha": "f" * 64})
    (d / "job.json").write_text(json.dumps(data))
    c = plan(svc)[1]
    assert c["summary"] == "ok"
    data["conversation"][1].pop("folder_sha")
    data["conversation"][1]["stage"] = "w0"
    (d / "job.json").write_text(json.dumps(data))
    c = plan(svc)[1]
    assert c["summary"] is None and "terikat" in c["summary_why"]


def test_the_cost_says_the_proposal_is_a_cap_for_all_issues_and_gives_it_per_issue(svc):
    t1, t2 = issue_text(SAME, AFTER), issue_text(AFTER, title="Second")
    d, _ = write_prd(svc.jobs, [t1, t2], [stored_for([SAME, AFTER]), stored_for([AFTER])])
    with_tree(d)
    cost = plan(svc)[1]["cost"]
    assert cost["proposed"] == 2.0 and cost["proposed_each"] == 1.0
    js = (Path(__file__).resolve().parent.parent / "router" / "chat_static" / "app.js").read_text()
    assert '"; batas antrean untuk "' in js and "(acuan: satu job)" in js


def test_a_key_prefix_never_survives_the_cut_of_the_request(svc):
    d = one(svc, [SAME, AFTER])
    data = json.loads((d / "job.json").read_text())
    data["conversation"][0]["text"] = "x" * (ac.REQUEST_MAX - 12) + "sk-proj-" + "a" * 40
    (d / "job.json").write_text(json.dumps(data))
    c = plan(svc)[1]
    assert "sk-" not in c["request"] and "sk-" not in json.dumps(c)


def test_a_missing_or_linked_or_foreign_source_tree_gets_its_own_reason(svc, tmp_path):
    d = one(svc, [SAME])
    import shutil
    src = d / "runs" / f"{PJOB}-w1" / "source"
    real = tmp_path / "elsewhere"
    shutil.move(str(src), str(real))
    os.symlink(real, src)                                              # a link: never followed
    e = ex_by_id(plan(svc)[1], "e1")
    assert e["showable"] is False and e["why"] == ac.TREE_WHY and [i["name"] for i in e["inputs"]] == ["argumen 1", "argumen 2"]
    os.remove(src)
    shutil.move(str(real), str(src))
    assert ex_by_id(plan(svc)[1], "e1")["showable"] is True
    data = json.loads((d / "job.json").read_text())
    data["stages"]["w1"]["run_id"] = "j20261117_100000_aaaa-w2"        # not the run of this turn
    (d / "job.json").write_text(json.dumps(data))
    assert ex_by_id(plan(svc)[1], "e1")["why"] == ac.TREE_WHY


def test_the_warning_also_comes_with_a_no_examples_reason_and_when_the_item_cannot_be_read(svc):
    stored = stored_for([SAME, AFTER])
    stored["no_examples"] = "because"
    one(svc, [SAME, AFTER], stored=stored)
    assert plan(svc)[1]["items"][0]["warning"] == ac.NO_NEW_WARNING
    leak = {**SAME, "setup": "from src.shop import total; k1 = 'sk-ant-'", "run": "'abcdefghij1234' and total([2, 3], 1)"}
    d, _ = write_prd(svc.jobs, [issue_text(leak)], [stored_for([leak])])
    with_tree(d)
    item = plan(svc)[1]["items"][0]
    assert item["examples"] == {"withheld": True} and item["warning"] == ac.NO_NEW_WARNING


def test_the_reference_needs_three_costs_counts_only_applied_code_jobs_and_ignores_non_finite(svc):
    one(svc, [SAME, AFTER])
    mk = lambda n, **kw: write_job(svc.jobs, f"j20261116_10{n:04d}_aaa{n % 10}", **kw)
    mk(1, kind="code", state="APPLIED", stages={"a1": {"kind": "agent", "usd": 0.1}})
    mk(2, kind="code", state="APPLIED", stages={"a1": {"kind": "agent", "usd": 0.3}})
    assert plan(svc)[1]["cost"]["reference"] is None                         # two are not enough
    mk(3, kind="research", state="APPLIED", stages={"a1": {"kind": "agent", "usd": 50.0}})
    mk(4, kind="code", state="APPLIED", stages={"a1": {"kind": "agent", "usd": float("nan")}})
    ref = plan(svc)[1]["cost"]["reference"]
    assert ref["median"] is None and ref["n"] == 2                           # a research job and a NaN do not count as costs (the NaN job still has its cap)
    mk(5, kind="code", state="APPLIED", stages={"a1": {"kind": "agent", "usd": 0.2}})
    assert plan(svc)[1]["cost"]["reference"] == {"median": 0.2, "n": 3, "of": ac.REFERENCE_OF, "cap_median": 1.0, "cap_n": 4}


def test_a_bool_or_non_finite_proposal_is_not_a_number(svc):
    for bad in (True, float("nan"), float("inf")):
        d = one(svc, [SAME, AFTER])
        data = json.loads((d / "job.json").read_text())
        data["prd_turns"][-1]["max_usd"] = bad
        (d / "job.json").write_text(json.dumps(data))
        c = plan(svc)
        assert c[0] == 200 and c[1]["cost"]["proposed"] is None and c[1]["cost"]["proposed_each"] is None


def test_the_request_is_cut_at_exactly_the_limit_and_is_the_first_human_message(svc):
    d = one(svc, [SAME, AFTER])
    data = json.loads((d / "job.json").read_text())
    data["conversation"].insert(1, {"from": "human", "text": "a second human message"})
    data["conversation"][0]["text"] = "y" * ac.REQUEST_MAX
    (d / "job.json").write_text(json.dumps(data))
    c = plan(svc)[1]
    assert c["request"] == "y" * ac.REQUEST_MAX and c["request_truncated"] is False
    data["conversation"][0]["text"] = "y" * (ac.REQUEST_MAX + 1)
    (d / "job.json").write_text(json.dumps(data))
    c = plan(svc)[1]
    assert c["request"] == "y" * ac.REQUEST_MAX and c["request_truncated"] is True


def test_the_missing_folder_sha_and_commit_are_not_the_word_none(svc):
    d = one(svc, [SAME, AFTER])
    data = json.loads((d / "job.json").read_text())
    data["prd_turns"][-1].pop("folder_sha")
    data["prd_turns"][-1].pop("commit")
    data["inputs"].pop("commit")
    (d / "job.json").write_text(json.dumps(data))
    c = plan(svc)[1]
    assert c["folder_sha12"] is None and c["stale"] is True


def test_the_plan_page_guards_old_answers_and_marks_the_author_honestly():
    js = (Path(__file__).resolve().parent.parent / "router" / "chat_static" / "app.js").read_text()
    part = js[js.index("function showPlan"):js.index("function installReader")]
    assert part.count('if (seq !== cardSeq || mode !== "cards") { return; }') == 2
    assert "if (d.defects) {" in part and 'el("p", "note", it.warning)' in js
    assert 'd.request_by === "chat"' in part and '"permintaan, dimulai lewat chat (tercatat via ui):"' in part and '"permintaan (pembuat tidak tercatat):"' in part
    assert "d.defects" in part and 'say(s2, "model", MODEL, d.summary, "say")' in part and 'say(d, "mesin", "mesin", e.proof.wording' in js
    assert 'function planItem' in js and '["same", "whatif", "after"].forEach' in js
    assert "function setMode(m) {\n    mode = m;\n    cardSeq++;" in js


def test_a_value_too_deep_to_write_is_worded_as_such(svc):
    deep = []
    for _ in range(3000):
        deep = [deep]
    p = ac.Approve._proof("same", {"status": "pass", "actual": deep}, None)
    assert p["wording"] == "kode sekarang memberi angka ini: nilai tidak bisa ditulis" and p["actual_json"] is None


def test_the_author_is_chat_only_for_the_created_entry(svc):
    d = one(svc, [SAME, AFTER])
    data = json.loads((d / "job.json").read_text())
    data["log"] = [{"what": "state", "via": "ui"}]
    (d / "job.json").write_text(json.dumps(data))
    assert plan(svc)[1]["request_by"] == "tidak_tercatat"


def test_the_summary_needs_both_the_stage_and_the_folder_sha(svc):
    d = one(svc, [SAME, AFTER])
    base = json.loads((d / "job.json").read_text())
    for patch in ({"stage": "w9"}, {"folder_sha": "e" * 64}):
        data = json.loads(json.dumps(base))
        data["conversation"][1].update(patch)
        (d / "job.json").write_text(json.dumps(data))
        assert plan(svc)[1]["summary"] is None, patch


def test_the_tree_of_another_run_is_never_used(svc):
    d = one(svc, [SAME])
    other = d / "runs" / f"{PJOB}-w2" / "source" / "src"
    other.mkdir(parents=True)
    (other / "__init__.py").write_text("")
    (other / "shop.py").write_text("def total(zzz, yyy):\n    return 0\n")
    data = json.loads((d / "job.json").read_text())
    data["stages"]["w1"]["run_id"] = f"{PJOB}-w2"
    (d / "job.json").write_text(json.dumps(data))
    e = ex_by_id(plan(svc)[1], "e1")
    assert [i["name"] for i in e["inputs"]] == ["argumen 1", "argumen 2"]


def test_a_turn_from_before_the_example_gate_says_so(svc):
    d = one(svc, [SAME])
    data = json.loads((d / "job.json").read_text())
    data["prd_turns"][-1].pop("examples")
    (d / "job.json").write_text(json.dumps(data))
    item = plan(svc)[1]["items"][0]
    assert item["why"] == "dari sebelum gerbang contoh" and "belum diperiksa mesin (dari sebelum gerbang contoh)" in item["examples"][0]["proof"]["wording"]


def test_a_tree_that_reads_but_lacks_the_definition_keeps_the_real_reason(svc):
    d = one(svc, [SAME])
    with_tree(d, "def other():\n    pass\n")
    e = ex_by_id(plan(svc)[1], "e1")
    assert e["showable"] is False and "nama parameter tidak ditemukan" in e["why"] and e["why"] != ac.TREE_WHY


def test_a_non_finite_spent_is_not_a_number(svc):
    d = one(svc, [SAME, AFTER])
    data = json.loads((d / "job.json").read_text())
    data["stages"]["w1"]["usd"] = float("nan")
    (d / "job.json").write_text(json.dumps(data))
    status, c = plan(svc)
    assert status == 200 and c["cost"]["spent"] is None


def test_an_item_with_no_stored_entry_is_not_run_yet_unlike_a_turn_from_before_the_gate(svc):
    d, _ = write_prd(svc.jobs, [issue_text(SAME), issue_text(AFTER, title="Two")], [stored_for([SAME]), None])
    with_tree(d)
    second = plan(svc)[1]["items"][1]
    assert second["why"] == NOT_RUN_WHY and "dijalankan saat job code item ini mulai" in second["examples"][0]["proof"]["wording"]


# ---- PR 4b: what the domain reader said, and the cost as a ratio ------------------------------------------------------------------

from types import SimpleNamespace  # noqa: E402
from router import examples_read as er  # noqa: E402

DEPS = SimpleNamespace(clock=lambda: "2026-11-17T10:00:00Z")


def reader_note(svc, item=1, verdict="ok", sources=("permintaan Atha",), note="the numbers fit the request", twice=True):
    text, info = er.bundle(svc.jobs, PJOB, item)
    out = er.record(PJOB, item, verdict, info["bundle_sha256"], "opus-7", list(sources), note, deps=DEPS, jobs_dir=svc.jobs)
    if twice and verdict == "ok":                                         # rev 3: an ok is two independent readings
        er.record(PJOB, item, verdict, info["bundle_sha256"], "opus-8", list(sources), note, deps=DEPS, jobs_dir=svc.jobs, second=True)
    return out


def dr(c, item=0):
    return c["items"][item]["domain_read"]


def test_the_card_says_the_domain_is_unread_until_a_reader_wrote_a_note(svc):
    one(svc, [SAME, AFTER])
    c = plan(svc)[1]
    assert c["domain_read_label"] == ac.DOMAIN_LABEL and "bukan manusia" in ac.DOMAIN_LABEL and "bukan bukti" in ac.DOMAIN_LABEL
    assert dr(c) == {"kind": "none", "fresh": False, "why": ac.DOMAIN_UNREAD}
    assert "belum dibaca" in ac.DOMAIN_UNREAD and "belum dinilai siapa pun" in ac.DOMAIN_UNREAD


def test_an_ok_and_a_concerns_note_are_shown_with_who_when_sources_and_the_note_as_model_text(svc):
    d = one(svc, [SAME, AFTER])
    (d / "runs" / f"{PJOB}-w1" / "source" / "README.md").write_text("The floor of a total is 0.\n")
    reader_note(svc, sources=("permintaan Atha", "dokumen repo: README.md"))
    d = dr(plan(svc)[1])
    assert d["kind"] == "ok" and d["fresh"] is True and d["verdict"] == "ok" and d["reader"] == {"kind": "claude", "id": "opus-7"}
    assert d["at"] == "2026-11-17T10:00:00Z" and d["sources"] == ["permintaan Atha", "dokumen repo: README.md"] and d["note"] == "the numbers fit the request"
    reader_note(svc, verdict="concerns", sources=("hanya tulisan penulis",), note="the 3% is only in the PRD")
    d = dr(plan(svc)[1])
    assert d["kind"] == "concerns" and d["fresh"] is True and d["note"] == "the 3% is only in the PRD"


def test_a_note_is_stale_when_anything_it_was_bound_to_changed(svc):
    d = one(svc, [SAME, AFTER])
    reader_note(svc)
    with_tree(d, "def total(a, b):\n    return 0\n")                                   # the numbers card changes: another bundle
    got = dr(plan(svc)[1])
    assert got["kind"] == "stale" and got["fresh"] is False and "note" not in got and "reader" not in got and got["why"] == ac.DOMAIN_STALE


def test_a_damaged_note_file_is_an_error_and_counts_as_unread(svc):
    d = one(svc, [SAME, AFTER])
    reader_note(svc)
    (d / "examples_read_w1.json").write_text("{")
    got = dr(plan(svc)[1])
    assert got["kind"] == "error" and got["fresh"] is False and got["why"] == ac.DOMAIN_ERROR


def test_an_item_without_examples_has_nothing_to_read_and_says_so(svc):
    stored = {"examples": [], "results": [], "no_examples": "the text is the contract", "note": None, "tier_moves": []}
    d, _ = write_prd(svc.jobs, [issue_text()], [stored])
    with_tree(d)
    got = dr(plan(svc)[1])
    assert got == {"kind": "tidak_berlaku", "fresh": False, "why": ac.DOMAIN_NONE}
    assert "tidak ada angka baru yang dibaca" in ac.DOMAIN_NONE


def test_a_folder_that_cannot_be_read_by_the_reader_is_said_not_hidden(svc):
    d = one(svc, [SAME, AFTER])
    reader_note(svc)
    (d / "prd-w1" / "SUPERSEDED").write_text("x")
    got = dr(plan(svc)[1])
    assert got["kind"] == "tidak_terbaca" and got["fresh"] is False and "SUPERSEDED" in got["why"]


def test_a_withheld_item_has_no_reading(svc):
    leak = {**SAME, "setup": "from src.shop import total; k1 = 'sk-ant-'", "run": "'abcdefghij1234' and total([2, 3], 1)"}
    d, _ = write_prd(svc.jobs, [issue_text(leak)], [stored_for([leak])])
    with_tree(d)
    item = plan(svc)[1]["items"][0]
    assert item["examples"] == {"withheld": True} and item["domain_read"]["kind"] == "tidak_terbaca"


def test_the_note_text_is_scrubbed_like_all_card_text(svc):
    one(svc, [SAME, AFTER])
    text, info = er.bundle(svc.jobs, PJOB, 1)
    reader_note(svc, note="fine\u202e end")
    assert "\u202e" not in json.dumps(plan(svc)[1], ensure_ascii=False)


def test_the_cost_ratio_compares_the_proposal_per_issue_with_the_caps_of_earlier_jobs_not_with_their_spending(svc):
    d, _ = write_prd(svc.jobs, [issue_text(SAME, AFTER), issue_text(AFTER, title="Second")], [stored_for([SAME, AFTER]), stored_for([AFTER])])
    with_tree(d)
    assert plan(svc)[1]["cost"]["ratio"] is None and plan(svc)[1]["cost"]["ratio_text"] is None           # no reference yet
    for n, usd in enumerate((0.10, 0.30, 0.20, 0.50), 1):
        write_job(svc.jobs, f"j20261116_10000{n}_aaa{n}", kind="code", state="APPLIED", stages={"a1": {"kind": "agent", "usd": usd}})
    cost = plan(svc)[1]["cost"]
    assert cost["proposed_each"] == 1.0 and cost["reference"]["cap_median"] == 1.0 and cost["reference"]["median"] == 0.25
    assert cost["ratio"] == 1.0 and cost["ratio_text"] == "kira-kira 1× batas job biasa per issue"          # not 4: spending is not the yardstick
    data = json.loads((d / "job.json").read_text())
    data["prd_turns"][-1]["max_usd"] = 6.6                                              # 3.3 per issue
    (d / "job.json").write_text(json.dumps(data))
    assert plan(svc)[1]["cost"]["ratio_text"] == "kira-kira 3,3× batas job biasa per issue"
    data["prd_turns"][-1]["max_usd"] = 0.2                                              # 0.1 per issue: below the usual
    (d / "job.json").write_text(json.dumps(data))
    assert plan(svc)[1]["cost"]["ratio_text"] == "kira-kira 0,1× batas job biasa per issue"


def test_without_three_known_caps_or_with_a_cap_of_zero_there_is_no_ratio(svc):
    one(svc, [SAME, AFTER])
    for n in range(1, 5):
        write_job(svc.jobs, f"j20261116_10000{n}_aaa{n}", kind="code", state="APPLIED", max_usd=0, stages={"a1": {"kind": "agent", "usd": 0.1}})
    cost = plan(svc)[1]["cost"]
    assert cost["reference"]["median"] == 0.1 and cost["reference"]["cap_median"] is None and cost["ratio"] is None and cost["ratio_text"] is None


def test_the_page_shows_the_reading_with_its_label_and_the_ratio():
    js = (Path(__file__).resolve().parent.parent / "router" / "chat_static" / "app.js").read_text()
    part = js[js.index("var DOMAIN_LABEL"):js.index("// ---- T2: read-only cards")]
    assert "it.domain_read" in part and "d.domain_read_label" in part and "d.cost.ratio_text" in part
    for word in ("Dibaca Claude", "ada yang meragukan"):
        assert word in part
    assert "innerHTML" not in part


# ---- the fixes of the review of PR 4b ---------------------------------------------------------------------------------------------

def test_a_key_pattern_in_the_readers_note_or_id_never_reaches_the_card(svc):
    d = one(svc, [SAME, AFTER])
    text, info = er.bundle(svc.jobs, PJOB, 1)
    er.record(PJOB, 1, "concerns", info["bundle_sha256"], "sk-ant-" + "b" * 30, ["hanya tulisan penulis"], "see sk-ant-" + "a" * 30, deps=DEPS, jobs_dir=svc.jobs)
    status, c = plan(svc)
    dump = json.dumps(c)
    assert status == 200 and "sk-ant" not in dump and "a" * 30 not in dump and "b" * 30 not in dump


def test_an_unreadable_issue_or_a_broken_block_is_not_no_examples(svc):
    d = one(svc, [SAME, AFTER])
    (d / "prd-w1" / "issue-1.md").write_text(issue_text(SAME).replace("```argus-examples", "```argus-examples json"))
    got = plan(svc)[1]["items"][0]["domain_read"]
    assert got["kind"] == "tidak_terbaca" and got["fresh"] is False


def test_the_refusal_texts_are_indonesian_and_do_not_carry_the_internal_wording(svc):
    d = one(svc, [SAME, AFTER])
    (d / "prd-w1" / "SUPERSEDED").write_text("x")
    why = dr(plan(svc)[1])["why"]
    assert "nothing was written" not in why and "SUPERSEDED" in why and "digantikan" in why


def test_a_ratio_below_one_keeps_two_digits(svc):
    d = one(svc, [SAME, AFTER])
    for n in range(1, 5):
        write_job(svc.jobs, f"j20261116_10000{n}_aaa{n}", kind="code", state="APPLIED", stages={"a1": {"kind": "agent", "usd": 0.1}})
    data = json.loads((d / "job.json").read_text())
    data["prd_turns"][-1]["max_usd"] = 0.04
    (d / "job.json").write_text(json.dumps(data))
    assert plan(svc)[1]["cost"]["ratio_text"] == "kira-kira 0,04× batas job biasa per issue"


def test_the_cap_reference_does_not_need_the_spending_to_be_known(svc):
    one(svc, [SAME, AFTER])
    for n in range(1, 4):
        write_job(svc.jobs, f"j20261116_10000{n}_aaa{n}", kind="code", state="APPLIED", stages={"a1": {"kind": "agent"}})      # spending unknown
    cost = plan(svc)[1]["cost"]
    assert cost["reference"]["median"] is None and cost["reference"]["cap_median"] == 1.0 and cost["reference"]["cap_n"] == 3
    assert cost["ratio_text"] == "kira-kira 2× batas job biasa per issue"                      # one issue, proposed 2.0, usual cap 1.0


def test_a_bool_infinite_or_zero_cap_is_no_cap_and_two_caps_are_too_few(svc):
    one(svc, [SAME, AFTER])
    for n, cap in enumerate((True, float("inf"), 0, 1.0, 1.0), 1):
        write_job(svc.jobs, f"j20261116_10000{n}_aaa{n}", kind="code", state="APPLIED", max_usd=cap, stages={"a1": {"kind": "agent", "usd": 0.1}})
    ref = plan(svc)[1]["cost"]["reference"]
    assert ref["cap_n"] == 2 and ref["cap_median"] is None                                      # two valid caps: not enough
    write_job(svc.jobs, "j20261116_100006_aaa6", kind="code", state="APPLIED", max_usd=2.0, stages={"a1": {"kind": "agent", "usd": 0.1}})
    ref = plan(svc)[1]["cost"]["reference"]
    assert ref["cap_n"] == 3 and ref["cap_median"] == 1.0                                       # the median of 1, 1, 2


def test_the_page_shows_the_label_next_to_every_reading_and_never_a_reading_without_it():
    js = (Path(__file__).resolve().parent.parent / "router" / "chat_static" / "app.js").read_text()
    reading = js[js.index("function planReading"):js.index("function planItem")]
    assert reading.count('box.appendChild(el("p", "small", DOMAIN_LABEL));') == 1                 # one fresh branch: ok and concerns are told apart inside it
    assert reading.index("if (!DOMAIN_LABEL)") < reading.index("Dibaca Claude")                  # no label, no reading
    assert "if (r.fresh) {" in reading and 'r.verdict === "ok" ? "sesuai permintaan" : "ada yang meragukan"' in reading
    assert reading.index("modelLine(box, r.note)") < reading.index('el("p", "small", DOMAIN_LABEL)')
    assert reading.count("modelLine(box, r.note)") == 1
    assert "r.note" not in reading.split("} else {")[-1]                                          # a stale or missing reading never shows a note
    plan_js = js[js.index("function showPlan"):js.index("function installReader")]
    assert plan_js.index("DOMAIN_LABEL = d.domain_read_label") < plan_js.index("(d.items || []).forEach")
    assert 'el("p", "note", "Dibaca Claude: basi' not in js and "batas itu pagar, bukan perkiraan biaya" in js


def test_an_unexpected_failure_of_the_reading_never_breaks_the_card_or_shows_a_reading(svc, monkeypatch):
    one(svc, [SAME, AFTER])
    reader_note(svc)
    monkeypatch.setattr(er, "status", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    status, c = plan(svc)
    got = c["items"][0]["domain_read"]
    assert status == 200 and got["kind"] == "tidak_terbaca" and got["fresh"] is False and "note" not in got and "boom" not in json.dumps(c)


def test_the_page_guards_a_card_without_a_reading():
    js = (Path(__file__).resolve().parent.parent / "router" / "chat_static" / "app.js").read_text()
    assert "    if (it.domain_read) { planReading(c, it.domain_read); }" in js


def test_one_reading_is_shown_as_one_not_as_a_reading(svc):
    one(svc, [SAME, AFTER])
    reader_note(svc, twice=False)
    d = dr(plan(svc)[1])
    assert d == {"kind": "one", "fresh": False, "why": ac.DOMAIN_ONE} and "dua bacaan" in ac.DOMAIN_ONE
    reader_note(svc, twice=True)
    assert dr(plan(svc)[1])["kind"] == "ok"
