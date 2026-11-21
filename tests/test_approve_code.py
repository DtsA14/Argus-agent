"""SPEC_KARTU_SETUJU PR 5b (T3): the install card, GET /api/approve/code/<job> (router/approve_code.py). One code job, one patch sha: the purpose and cost
for the human, the examples as numbers with the audit's proof words, the files the patch touches with the machine's scope marks, the notes of the two
Claude readers marked as such, and the conditions (a) to (i) of section 3: block C is open only when all of them hold, and each one closes it alone.
Real files in a temporary jobs directory, a real server on a free port; no model, no Docker, no process."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_approve_plan import SHOP, with_tree  # noqa: E402
from test_chat_cards import AFTER, PJOB, QID, SAME, issue_text, stored_for, svc, write_job, write_prd  # noqa: E402,F401

from router import approve_code as acode  # noqa: E402
from router import examples_read as er  # noqa: E402
from router import patch_read as pr  # noqa: E402
from router import example_gate as eg  # noqa: E402

CJOB = "j20261117_100200_cccc"
SNAP = "5" * 64


def build_patch(files, bodies=None):
    return "".join(f"diff --git a/{p} b/{p}\n--- a/{p}\n+++ b/{p}\n@@ -1 +1 @@\n-x\n+{(bodies or {}).get(p, 'y')}\n" for p in files).encode()


PATCH = build_patch(("src/shop.py",))
PSHA = hashlib.sha256(PATCH).hexdigest()
WHATIF = {"id": "e3", "tier": "whatif", "says": "With a floor of 5 a total of 2 is 5", "setup": "import src.shop as shop",
          "run": "shop.total([2], 0)", "expect": 5, "overrides": {"src.shop.FLOOR": 5}}
KEYS = "abcdefghi"


def make(s, jid=CJOB, examples=(SAME, AFTER), *, base="pass", audit="pass", review_valid=True, state="REVIEW_READY", approval=True,
         read="ok", prov_sha=None, read_sha=None, files=("src/shop.py",), protected=(), text=None, approved_draft="d" * 64, patch_sha=None, cap=0.5,
         note="read the diff: only the floor changed", by_reader="claude", bodies=None, sid="a1", base_fail=(), one_reading=False):
    """A code job as the files of a real one: job.json, the review package, the examples intake and audit, the patch reader's note."""
    text = text if text is not None else issue_text(*examples)
    patch = build_patch(files, bodies)
    parsed = eg.extract(text)[1] if examples else []
    psha = patch_sha or hashlib.sha256(patch).hexdigest()
    run = f"{jid}-{sid}"
    d = write_job(s.jobs, jid, kind="code", state=state, max_usd=cap,
                  inputs={"repo": "/secret/path", "repo_name": "athena", "commit": "c" * 40, "issue": text, "environment": "athena_py312"},
                  intake={"snapshot_sha256": SNAP, "commit": "c" * 40},
                  stages={"d1": {"kind": "draft", "status": "DRAFTED", "run_id": f"{jid}-d1", "draft_sha256": "d" * 64, "usd": 0.01},
                          sid: {"kind": "agent", "status": "DONE", "run_id": run, "usd": 0.04,
                                 "review": {"valid": review_valid, "problems": [], "dir": f"/x/{run}/review", "patch_sha256": psha}}},
                  approval=({"draft_sha256": approved_draft, "contract_sha256": "e" * 64, "max_usd": cap, "at": "2026-11-18T01:00:00Z", "by": "ubuntu"}
                            if approval else None),
                  protected_repo={"globs": list(protected)}, log=[])
    if not approval:
        j = json.loads((d / "job.json").read_text())
        j.pop("approval")
        (d / "job.json").write_text(json.dumps(j))
    rev = d / "runs" / run / "review"
    rev.mkdir(parents=True)
    (rev / "changes.patch").write_bytes(patch)
    tree = d / "runs" / run / "workspace" / "src"
    tree.mkdir(parents=True)
    (tree / "__init__.py").write_text("")
    (tree / "shop.py").write_text(SHOP)
    (rev / "provenance.json").write_text(json.dumps({"patch": {"sha256": prov_sha or hashlib.sha256(patch).hexdigest(),
                                                               "files": [{"path": p} for p in files]}}))
    if parsed:
        base_rows = [{"id": e["id"], "tier": e["tier"], "status": "unchecked", "base_actual": -4} if e["tier"] == "after"
                     else {"id": e["id"], "tier": e["tier"], "status": "fail" if base == "fail" or e["id"] in base_fail else "pass", "actual": e["expect"]} for e in parsed]
        eg.store(d / eg.INTAKE_FILE, eg.intake_key(SNAP, parsed), results=base_rows)
        rows = [{"id": e["id"], "tier": e["tier"], "status": "fail" if audit == "fail" and e["tier"] == "after" else "pass",
                 "actual": 7 if audit == "fail" and e["tier"] == "after" else e["expect"]} for e in parsed]
        eg.store(eg.audit_file(d, sid), eg.audit_key(psha, parsed), results=rows)
    if read:
        (d / f"patch_read_{sid}.json").write_text(json.dumps({
            "key": pr.key(sid, read_sha or psha), "sid": sid, "patch_sha256": read_sha or psha, "verdict": read, "note": note,
            "at": "2026-11-18T01:30:00Z", "reader": {"kind": by_reader, "id": "opus-1"}, **({"template_sha256": pr.TEMPLATE_SHA256} if by_reader == "argus" else {}),
            **({"second": {"verdict": read, "note": note, "at": "2026-11-18T01:31:00Z", "reader": {"kind": by_reader, "id": "opus-2"},
                           **({"template_sha256": pr.TEMPLATE_SHA256} if by_reader == "argus" else {})}} if read == "ok" and not one_reading else {})}))
    return d


def get(s, jid=CJOB):
    return s.request("GET", f"/api/approve/code/{jid}")


def checks(c):
    return {x["key"]: x for x in c["checks"]}


def good(s, **kw):
    make(s, **kw)
    status, c = get(s)
    assert status == 200
    return c


# ---- the whole card, and each condition alone ---------------------------------------------------------------------------------

def test_a_complete_job_opens_c_with_every_condition_true_and_says_who_read(svc):
    c = good(svc)
    k = checks(c)
    assert list(k) == list(KEYS) and c["open"] is True
    assert all(k[x]["ok"] in (True, None) for x in KEYS) and k["f"]["ok"] is True and k["i"]["ok"] is None            # (i) does not apply: not from a PRD
    assert c["kind"] == "install" and c["id"] == CJOB and c["sid"] == "a1" and c["patch_sha12"] == PSHA[:12]
    assert c["patch_read"]["verdict"] == "ok" and c["patch_read"]["reader"] == {"kind": "claude", "id": "opus-1"}
    assert c["patch_read"]["second"]["reader"] == {"kind": "claude", "id": "opus-2"} and c["patch_read"]["second"]["verdict"] == "ok"
    assert "bukan dibaca manusia" in c["patch_read_label"] and "bukan manusia" in c["domain_read_label"]
    assert c["purpose"]["title"] == "total() never goes below zero" and c["files"] == [{"path": "src/shop.py", "marks": []}]


@pytest.mark.parametrize("key,kw", [
    ("a", {"base": "fail"}),
    ("b", {"audit": "fail"}),
    ("c", {"review_valid": False}),
    ("c", {"state": "REVIEW_INVALID"}),
    ("d", {"approval": False}),
    ("e", {"approval": False}),
    ("e", {"approved_draft": "9" * 64}),
    ("f", {"read": None}),
    ("f", {"read": "concerns"}),
    ("f", {"read_sha": "8" * 64}),
    ("f", {"by_reader": "human"}),
    ("g", {"prov_sha": "8" * 64}),
    ("h", {"examples": (SAME,)}),
    ("h", {"examples": ()}),
])
def test_each_condition_closes_c_alone_and_says_what_is_missing(svc, key, kw):
    c = good(svc, **kw)
    k = checks(c)
    assert k[key]["ok"] is False and k[key]["why"] and c["open"] is False
    others = {x for x in KEYS if k[x]["ok"] is False}
    assert key in others


def test_the_patch_on_disk_must_be_the_one_the_review_recorded(svc):
    c = good(svc, patch_sha="6" * 64)                       # job.json names another patch than changes.patch holds
    assert checks(c)["g"]["ok"] is False and c["open"] is False


def test_a_missing_file_closes_the_condition_it_feeds_and_never_opens_c(svc):
    d = make(svc)
    (d / "examples_audit_a1.json").unlink()
    c = get(svc)[1]
    assert checks(c)["b"]["ok"] is False and c["open"] is False
    (d / "examples_intake.json").unlink()
    assert checks(get(svc)[1])["a"]["ok"] is False


def test_a_damaged_patch_read_note_closes_f_and_is_not_shown_as_a_reading(svc):
    d = make(svc)
    (d / "patch_read_a1.json").write_text("{")
    c = get(svc)[1]
    assert checks(c)["f"]["ok"] is False and c["patch_read"] is None and c["open"] is False


def test_a_patch_read_note_that_is_a_link_is_not_followed(svc, tmp_path):
    d = make(svc)
    (d / "patch_read_a1.json").unlink()
    other = tmp_path / "elsewhere.json"
    other.write_text(json.dumps({"verdict": "ok"}))
    (d / "patch_read_a1.json").symlink_to(other)
    assert checks(get(svc)[1])["f"]["ok"] is False


# ---- the examples as numbers, with the audit's words ---------------------------------------------------------------------------

def test_the_audit_proof_says_the_final_code_gave_this_and_that_it_matches(svc):
    c = good(svc, examples=(SAME, AFTER, WHATIF))
    ex = c["item"]["examples"]
    assert [e["tier"] for e in ex] == ["same", "whatif", "after"]
    after = [e for e in ex if e["tier"] == "after"][0]["proof"]
    assert after["kind"] == "audit" and after["status"] == "pass" and after["wording"] == "kode akhir memberi angka ini: 0; cocok dengan yang diharapkan"
    same = [e for e in ex if e["tier"] == "same"][0]["proof"]
    assert same["wording"] == "kode akhir memberi angka ini: 4; cocok dengan yang diharapkan"


def test_a_failed_example_says_not_matching_and_never_matching(svc):
    c = good(svc, audit="fail")
    after = [e for e in c["item"]["examples"] if e["tier"] == "after"][0]["proof"]
    assert after["status"] == "fail" and after["wording"] == "kode akhir memberi angka ini: 7; TIDAK cocok dengan yang diharapkan"
    assert all("sengaja berubah" not in e["proof"]["wording"] for e in c["item"]["examples"])      # an allowed failure is not declared anywhere yet: C stays closed
    assert checks(c)["b"]["ok"] is False


def test_without_the_audit_for_this_patch_no_example_gets_a_proof(svc):
    d = make(svc)
    rows = json.loads((d / "examples_audit_a1.json").read_text())
    rows["key"] = "0" * 64
    (d / "examples_audit_a1.json").write_text(json.dumps(rows))
    c = get(svc)[1]
    assert all(e["proof"]["status"] is None for e in c["item"]["examples"]) and checks(c)["b"]["ok"] is False


def test_the_word_safe_is_never_in_the_card(svc):
    c = good(svc)
    text = json.dumps(c, ensure_ascii=False).lower()
    assert "aman" not in text.replace("amanda", "") and "safe" not in text


# ---- scope: the files, with the machine's marks -------------------------------------------------------------------------------

def test_a_protected_file_is_marked_and_listed(svc):
    c = good(svc, files=("src/shop.py", "config/secret.yaml"), protected=("config/*",))
    assert c["files"][1] == {"path": "src/shop.py", "marks": []}
    assert c["files"][0]["path"] == "config/secret.yaml" and c["files"][0]["marks"] == ["dilindungi repo (.argus/protected)"]
    assert c["scope_marks"] == ["config/secret.yaml: dilindungi repo (.argus/protected)"]
    assert checks(c)["c"]["ok"] is False and c["open"] is False                  # `argus apply` refuses a patch that touches a protected path


def test_the_purpose_cost_and_scope_are_there_for_the_human(svc):
    c = good(svc, cap=0.5)
    assert c["cost"]["cap"] == 0.5 and c["cost"]["spent"] == pytest.approx(0.05) and c["purpose"]["text"].startswith("A discount larger")


# ---- (i): the domain reader, through the chain queue -> PRD folder -> item -> digest ------------------------------------------------

def prd_world(s, **kw):
    """A PRD job whose folder item 1 is this code job's issue, and a queue made from it whose item 1 is the code job."""
    text = issue_text(SAME, AFTER)
    d, files = write_prd(s.jobs, [text + "\n"], [stored_for([SAME, AFTER])])
    with_tree(d)
    (d / "runs" / f"{PJOB}-w1" / "source" / "README.md").write_text("The floor of a total is 0.\n")
    code = make(s, text=text.strip(), **kw)
    q = s.queues / QID
    q.mkdir(exist_ok=True)
    (q / "queue.json").write_text(json.dumps({
        "id": QID, "repo": "/secret/path", "name": "athena", "base_commit": "c" * 40, "jobs_dir": str(s.jobs), "max_usd": 2.0, "job_cap_usd": 0.5,
        "environment": "athena_py312",
        "items": [{"n": 1, "issue_sha256": hashlib.sha256(text.strip().encode()).hexdigest(), "job": CJOB}],
        "prd": {"sha": json.loads((d / "job.json").read_text())["prd_turns"][-1]["folder_sha"], "dir": str(d / "prd-w1")}}))
    return d, code


def reader_note(s, verdict="ok", sources=("permintaan Atha",), note="the numbers fit the request", twice=True):
    _, info = er.bundle(s.jobs, PJOB, 1)
    deps = SimpleNamespace(clock=lambda: "2026-11-18T01:10:00Z")
    out = er.record(PJOB, 1, verdict, info["bundle_sha256"], "opus-7", list(sources), note, deps=deps, jobs_dir=s.jobs)
    if twice and verdict == "ok":                                         # rev 3: an ok is two independent readings
        er.record(PJOB, 1, verdict, info["bundle_sha256"], "opus-8", list(sources), note, deps=deps, jobs_dir=s.jobs, second=True)
    return out


def test_an_item_of_a_prd_queue_needs_the_domain_note_to_open_c(svc):
    prd_world(svc)
    c = get(svc)[1]
    k = checks(c)
    assert k["i"]["ok"] is False and c["open"] is False and "belum dibaca" in c["item"]["domain_read"]["why"]


def test_a_fresh_ok_domain_note_opens_i_and_c_and_is_marked_as_claude(svc):
    prd_world(svc)
    reader_note(svc)
    c = get(svc)[1]
    assert checks(c)["i"]["ok"] is True and c["open"] is True
    dr = c["item"]["domain_read"]
    assert dr["kind"] == "ok" and dr["fresh"] is True and "opus-7" in json.dumps(dr["reader"])
    assert "bukan manusia" in c["domain_read_label"]


def test_concerns_and_a_stale_domain_note_close_i(svc):
    d, _ = prd_world(svc)
    reader_note(svc, verdict="concerns", sources=("hanya tulisan penulis",), note="the 3% is only in the PRD")
    c = get(svc)[1]
    assert checks(c)["i"]["ok"] is False and c["open"] is False and c["item"]["domain_read"]["kind"] == "concerns"
    (d / "runs" / f"{PJOB}-w1" / "source" / "README.md").write_text("The floor is 5.\n")       # what the reader read changed
    c = get(svc)[1]
    assert checks(c)["i"]["ok"] is False and c["item"]["domain_read"]["kind"] == "stale"
    reader_note(svc)                                                                          # a new reading of the new bundle: the concerns was of the old one
    assert checks(get(svc)[1])["i"]["ok"] is True


def test_a_queue_that_names_the_job_but_cannot_be_used_closes_i(svc):
    prd_world(svc)
    reader_note(svc)
    (svc.queues / QID / "queue.json").write_text('{"id": "' + QID + '", "items": [{"job": "' + CJOB + '"')
    c = get(svc)[1]
    assert checks(c)["i"]["ok"] is False and c["open"] is False


def test_scope_marks_flag_a_file_outside_what_the_issue_said_it_touches_or_creates(svc):
    prd_world(svc, files=("src/shop.py", "show_floor", "src/other.py"), bodies={"src/shop.py": "def total", "show_floor": "show_floor"})
    c = get(svc)[1]
    marks = {f["path"]: f["marks"] for f in c["files"]}
    assert marks["src/other.py"] == ["di luar yang disebut issue (touches/creates)"] and marks["show_floor"] == [] and c["scope_marks"]


# ---- the readers have not been tested yet ----------------------------------------------------------------------------------------

def test_the_readers_are_untested_unless_the_record_holds_the_current_template_hash(svc, tmp_path, monkeypatch):
    f = tmp_path / "reader_tests.json"
    monkeypatch.setattr(acode, "READER_TESTS", f)
    prd_world(svc)
    reader_note(svc)
    c = get(svc)[1]
    assert c["patch_reader_tested"] is False and c["domain_reader_tested"] is False
    f.write_text(json.dumps({"athena": {"domain": {"template_sha256": er.TEMPLATE_SHA256, "model": "opus", "effort": "high", "passed_at": "2026-11-18", "evidence": "x"}}}))
    c = get(svc)[1]
    assert c["domain_reader_tested"] is True and c["patch_reader_tested"] is False        # the readers of the card are opus-7 and opus-8
    f.write_text(json.dumps({"athena": {"domain": {"template_sha256": er.TEMPLATE_SHA256, "model": "argus:z-ai/glm", "effort": "high"}}}))
    assert get(svc)[1]["domain_reader_tested"] is False                                     # a test of another model is not a test of these readers (13.3)
    f.write_text(json.dumps({"athena": {"domain": {"template_sha256": er.TEMPLATE_SHA256, "model": "opus"}}}))
    assert get(svc)[1]["domain_reader_tested"] is False                                     # no effort recorded
    f.write_text(json.dumps({"athena": {"domain": {"template_sha256": "0" * 64, "passed_at": "2026-11-18", "evidence": "x"}}}))
    assert get(svc)[1]["domain_reader_tested"] is False
    f.write_text("{")
    assert get(svc)[1]["domain_reader_tested"] is False
    f.write_text(json.dumps({"other-repo": {"domain": {"template_sha256": er.TEMPLATE_SHA256}}}))
    assert get(svc)[1]["domain_reader_tested"] is False


# ---- read only, GET only, nothing leaks ---------------------------------------------------------------------------------------------

def test_the_card_writes_nothing_and_starts_no_process(svc, monkeypatch):
    d = make(svc)
    before = sorted(str(p.relative_to(d)) + str(p.stat().st_size) for p in d.rglob("*"))
    def no_process(*a, **k):
        raise AssertionError("a process")
    for name in ("Popen", "run", "call", "check_output"):
        monkeypatch.setattr(subprocess, name, no_process)
    assert get(svc)[0] == 200
    assert sorted(str(p.relative_to(d)) + str(p.stat().st_size) for p in d.rglob("*")) == before


@pytest.mark.parametrize("job", ["nope", "j20261117_100200_zzzz", "../x", PJOB])
def test_no_card_for_an_unknown_id_or_a_job_that_is_not_code(svc, job):
    write_prd(svc.jobs, [issue_text(SAME)], [stored_for([SAME])])
    assert get(svc, job)[0] == 404


def test_only_get_is_allowed(svc):
    make(svc)
    assert svc.request("POST", f"/api/approve/code/{CJOB}")[0] in (404, 405)


def test_a_key_in_a_note_or_the_title_is_withheld_not_shown(svc):
    c = good(svc, note="found sk-ant-" + "a" * 30 + " in the diff", text=issue_text(SAME, AFTER, title="Fix sk-ant-" + "b" * 30))
    text = json.dumps(c)
    assert "sk-ant-" not in text


def test_the_card_never_names_the_repository_path(svc):
    assert "/secret/path" not in json.dumps(good(svc))


def test_a_damaged_job_json_gives_no_card_not_an_error(svc):
    d = make(svc)
    (d / "job.json").write_text("{")
    assert get(svc)[0] == 404


# ---- the page ------------------------------------------------------------------------------------------------------------------------

def test_the_page_has_an_install_view_reached_from_a_review_ready_queue_item_and_writes_only_text():
    js = (Path(__file__).resolve().parent.parent / "router" / "chat_static" / "app.js").read_text()
    assert js.count('get("/api/approve/code/" + encodeURIComponent(id))') == 1
    assert 'inst.addEventListener("click", function () { showInstall(it.job); });' in js and 'it.job_state === "REVIEW_READY"' in js
    part = js[js.index("function showInstall"):js.index("// ---- T2: read-only cards")]
    assert part.count('if (seq !== cardSeq || mode !== "cards") { return; }') == 2 and part.count("cardButtons()") == 2
    assert "innerHTML" not in part and "insertAdjacentHTML" not in part and "document.write" not in part
    assert "d.patch_read_label" in part and "d.domain_read_label" in part and "d.fixed_line" in part
    assert "pembaca patch belum diuji" in part and "pembaca angka belum diuji" in part and "TIDAK" in part
    assert "aman" not in part.replace("Ini bukan jaminan aman", "")              # the one place the word is, to deny it
    assert "fetch(" not in part and "XMLHttpRequest" not in part and "localStorage" not in part


# ---- what the review of the card found --------------------------------------------------------------------------------------------------

def edit_job(d, fn):
    f = d / "job.json"
    j = json.loads(f.read_text())
    fn(j)
    f.write_text(json.dumps(j))


def test_an_empty_patch_closes_g_because_apply_refuses_it(svc):
    c = good(svc, files=())
    assert checks(c)["g"]["ok"] is False and c["open"] is False


def test_a_whatif_that_fails_on_the_base_closes_a_with_the_tier_from_the_issue(svc):
    c = good(svc, examples=(SAME, AFTER, WHATIF), base_fail=("e3",))
    assert checks(c)["a"]["ok"] is False and "e3" in checks(c)["a"]["why"] and c["open"] is False


def test_the_tier_of_a_stored_row_does_not_decide_what_may_fail(svc):
    d = make(svc, examples=(SAME, AFTER))
    f = d / "examples_intake.json"
    doc = json.loads(f.read_text())
    for r in doc["results"]:
        if r["id"] == "e1":
            r["tier"], r["status"] = "after", "fail"                    # a `same` example that fails, relabelled in the file
    f.write_text(json.dumps(doc))
    c = get(svc)[1]
    assert checks(c)["a"]["ok"] is False and c["open"] is False


@pytest.mark.parametrize("name,kw", [("skipped", {"skipped": "no runner"}), ("pending", {"reason": "died"})])
@pytest.mark.parametrize("key,file", [("a", "examples_intake.json"), ("b", "examples_audit_a1.json")])
def test_a_skipped_or_unfinished_run_closes_the_condition(svc, name, kw, key, file):
    d = make(svc)
    doc = json.loads((d / file).read_text())
    eg.store(d / file, doc["key"], **kw)
    c = get(svc)[1]
    assert checks(c)[key]["ok"] is False and c["open"] is False
    assert ("belum selesai" in checks(c)[key]["why"]) == (name == "pending") and ("tidak dijalankan" in checks(c)[key]["why"]) == (name == "skipped")


def test_d_is_not_claimed_as_a_record_and_does_not_close_c(svc):
    c = good(svc)
    d = checks(c)["d"]
    assert d["ok"] is None and "tidak tercatat" in d["why"] and c["open"] is True


def test_review_problems_close_c_even_when_valid_is_true(svc):
    d = make(svc)
    edit_job(d, lambda j: j["stages"]["a1"]["review"].update(problems=["a rerun test failed"]))
    c = get(svc)[1]
    assert checks(c)["c"]["ok"] is False and c["open"] is False


def test_the_last_agent_stage_is_by_number_not_by_text(svc):
    d = make(svc, sid="a10")
    edit_job(d, lambda j: j["stages"].update(a2={"kind": "agent", "status": "DONE", "run_id": f"{CJOB}-a2", "review": {"valid": False, "problems": []}}))
    c = get(svc)[1]
    assert c["sid"] == "a10" and c["open"] is True


def test_the_approval_must_be_for_the_last_drafted_draft(svc):
    d = make(svc)
    edit_job(d, lambda j: j["stages"].update(d1={"kind": "draft", "status": "DRAFTED", "run_id": f"{CJOB}-d1", "draft_sha256": "1" * 64},
                                             d2={"kind": "draft", "status": "DRAFTED", "run_id": f"{CJOB}-d2", "draft_sha256": "d" * 64}))
    assert checks(get(svc)[1])["e"]["ok"] is True
    edit_job(d, lambda j: j["stages"].update(d1={"kind": "draft", "status": "DRAFTED", "run_id": f"{CJOB}-d1", "draft_sha256": "d" * 64},
                                             d2={"kind": "draft", "status": "DRAFTED", "run_id": f"{CJOB}-d2", "draft_sha256": "1" * 64}))
    assert checks(get(svc)[1])["e"]["ok"] is False


def test_a_stage_whose_run_id_names_another_job_is_not_read(svc):
    import shutil
    d = make(svc)
    other = d / "runs" / "j20261117_999999_ffff-a1"
    shutil.copytree(d / "runs" / f"{CJOB}-a1", other)                       # a complete package of another job, one that would open C if it were read
    edit_job(d, lambda j: j["stages"]["a1"].update(run_id="j20261117_999999_ffff-a1"))
    c = get(svc)[1]
    assert checks(c)["g"]["ok"] is False and c["open"] is False and c["files"] == []


def test_a_patch_that_is_a_pipe_or_too_large_or_a_link_is_not_read(svc, monkeypatch):
    import os
    d = make(svc)
    p = d / "runs" / f"{CJOB}-a1" / "review" / "changes.patch"
    p.unlink()
    os.mkfifo(p)
    assert checks(get(svc)[1])["g"]["ok"] is False                          # returns, does not wait for a writer
    p.unlink()
    p.write_bytes(PATCH)
    assert checks(get(svc)[1])["g"]["ok"] is True
    monkeypatch.setattr(acode, "PATCH_MAX", 10)
    assert checks(get(svc)[1])["g"]["ok"] is False


def test_a_job_directory_that_is_a_link_gives_no_card(svc):
    make(svc)
    (svc.jobs / "j20261117_100300_dddd").symlink_to(svc.jobs / CJOB)
    assert get(svc, "j20261117_100300_dddd")[0] == 404


def test_more_files_than_the_card_shows_are_counted_not_dropped_silently(svc):
    files = tuple(f"src/f{i:03d}.py" for i in range(acode.FILES_MAX + 5))
    c = good(svc, files=files)
    assert len(c["files"]) == acode.FILES_MAX and c["files_cut"] == 5


def test_the_card_says_when_the_scope_could_not_be_compared_with_the_issue(svc):
    c = good(svc)
    assert c["scope_note"] and "tidak diperiksa" in c["scope_note"]


def test_the_anchors_of_a_prd_item_ignore_lines_shorter_than_three_characters(svc):
    prd_world(svc)
    d = svc.jobs / PJOB
    edit_job(d, lambda j: j["prd_turns"][-1].update(touches=[["ab", "  ", "def total"]], creates=[["", "show_floor"]]))
    assert svc.actions.approve_code._anchors({"prd_job": PJOB, "item": 1}) == ["def total", "show_floor"]


def test_the_issue_is_marked_as_model_text_when_it_comes_from_a_prd(svc):
    prd_world(svc)
    assert "ditulis model" in get(svc)[1]["purpose"]["by"]


def test_an_issue_of_unknown_origin_says_the_maker_is_not_recorded(svc):
    assert "tidak tercatat" in good(svc)["purpose"]["by"]


def test_the_patch_reader_note_is_marked_as_model_text(svc):
    assert good(svc)["patch_read"]["by"] == "model"


def test_a_reader_test_entry_without_a_template_hash_is_not_a_pass(svc, tmp_path, monkeypatch):
    f = tmp_path / "reader_tests.json"
    monkeypatch.setattr(acode, "READER_TESTS", f)
    f.write_text(json.dumps({"athena": {"patch": {"template_sha256": None}, "domain": {"template_sha256": None}}}))
    c = good(svc)
    assert c["patch_reader_tested"] is False and c["domain_reader_tested"] is False


def test_an_audit_row_without_a_number_says_so_and_does_not_match(svc):
    d = make(svc)
    f = d / "examples_audit_a1.json"
    doc = json.loads(f.read_text())
    for r in doc["results"]:
        if r["tier"] == "after":
            r.pop("actual")
            r["status"] = "error"
    f.write_text(json.dumps(doc))
    c = get(svc)[1]
    after = [e for e in c["item"]["examples"] if e["tier"] == "after"][0]["proof"]
    assert after["wording"] == "kode akhir tidak memberi angka (gerbang menandai: error); TIDAK cocok dengan yang diharapkan"


def test_a_review_without_a_valid_field_is_not_valid(svc):
    d = make(svc)
    edit_job(d, lambda j: j["stages"]["a1"]["review"].pop("valid"))
    c = get(svc)[1]
    assert checks(c)["c"]["ok"] is False and c["open"] is False


def test_a_whatif_alone_is_an_example_of_the_new_behaviour(svc):
    c = good(svc, examples=(SAME, WHATIF))
    assert checks(c)["h"]["ok"] is True


def test_an_example_outside_the_grammar_closes_h(svc):
    odd = {"id": "e4", "tier": "after", "says": "odd", "setup": "x = 1", "run": "x", "expect": 1}
    c = good(svc, examples=(SAME, odd))
    assert checks(c)["h"]["ok"] is False and "tidak bisa ditampilkan" in checks(c)["h"]["why"] and c["open"] is False


def test_a_glob_that_cannot_be_read_protects(svc, monkeypatch):
    def boom(path, globs):
        raise ValueError("bad glob")
    monkeypatch.setattr(acode, "matches", boom)
    c = good(svc, protected=("x/*",))
    assert c["files"][0]["marks"] == [acode.PROTECTED_MARK] and c["open"] is False


def test_a_test_record_is_not_a_pass_for_a_card_without_a_reading(svc, tmp_path, monkeypatch):
    f = tmp_path / "reader_tests.json"
    monkeypatch.setattr(acode, "READER_TESTS", f)
    f.write_text(json.dumps({"athena": {"domain": {"template_sha256": er.TEMPLATE_SHA256, "model": "opus", "effort": "high"}}}))
    c = good(svc)
    assert c["item"]["domain_read"]["kind"] != "ok" and c["domain_reader_tested"] is False


def test_one_patch_reading_is_not_an_ok_and_two_by_the_same_id_are_not_two(svc):
    make(svc, one_reading=True)
    c = get(svc)[1]
    assert checks(c)["f"]["ok"] is False and "baru satu bacaan" in checks(c)["f"]["why"] and c["open"] is False and c["patch_read"] is None
    d = svc.jobs / CJOB
    f = d / "patch_read_a1.json"
    rec = json.loads(f.read_text())
    rec["second"] = {"verdict": "ok", "note": rec["note"], "at": "2026-11-18T01:31:00Z", "reader": {"kind": "claude", "id": " OPUS-1 "}}
    f.write_text(json.dumps(rec))
    c = get(svc)[1]
    assert checks(c)["f"]["ok"] is False                                                     # the same id, spelled otherwise: not a second reader
    rec["second"]["reader"]["id"] = "opus-2"
    rec["second"]["verdict"] = "concerns"
    f.write_text(json.dumps(rec))
    c = get(svc)[1]
    assert checks(c)["f"]["ok"] is False and c["patch_read"]["verdict"] == "concerns"        # a concerns of the second closes it and is what is shown


def test_the_patch_reader_is_tested_only_for_the_pair_of_models_and_the_template_that_were_tested(svc, tmp_path, monkeypatch):
    f = tmp_path / "reader_tests.json"
    monkeypatch.setattr(acode, "READER_TESTS", f)
    make(svc, by_reader="argus")
    rec = json.loads((svc.jobs / CJOB / "patch_read_a1.json").read_text())
    rec["reader"]["id"], rec["second"]["reader"]["id"] = "argus:openrouter:tencent/hy4-flash", "argus:openrouter:deepseek/deepseek-v4.1-flash-1017"
    (svc.jobs / CJOB / "patch_read_a1.json").write_text(json.dumps(rec))
    entry = {"template_sha256": pr.TEMPLATE_SHA256, "instruction_sha256": pr.INSTRUCTION_SHA256, "effort": "default", "models": ["argus:openrouter:tencent/hy4-flash", "argus:openrouter:deepseek/deepseek-v4.1-flash-1017"]}
    f.write_text(json.dumps({"athena": {"patch": entry}}))
    assert get(svc)[1]["patch_reader_tested"] is True
    for bad in ({**entry, "models": entry["models"][::-1]}, {**entry, "models": entry["models"][:1]}, {**entry, "template_sha256": "0" * 64}, {**entry, "effort": None},
                {k: v for k, v in entry.items() if k != "models"}):
        f.write_text(json.dumps({"athena": {"patch": bad}}))
        assert get(svc)[1]["patch_reader_tested"] is False
    f.write_text(json.dumps({"athena": {"patch": entry}}))
    # a Claude session that writes the ids of the pair is not the pair (the kind is checked), and so is a record without the instruction hash or at another effort
    rec = json.loads((svc.jobs / CJOB / "patch_read_a1.json").read_text())
    rec["reader"]["kind"] = "claude"
    (svc.jobs / CJOB / "patch_read_a1.json").write_text(json.dumps(rec))
    assert get(svc)[1]["patch_reader_tested"] is False
    rec["reader"]["kind"] = "argus"
    (svc.jobs / CJOB / "patch_read_a1.json").write_text(json.dumps(rec))
    for bad in ({**entry, "instruction_sha256": "0" * 64}, {**entry, "effort": "high"}):
        f.write_text(json.dumps({"athena": {"patch": bad}}))
        assert get(svc)[1]["patch_reader_tested"] is False
    f.write_text(json.dumps({"athena": {"patch": entry}}))
    assert get(svc)[1]["patch_reader_tested"] is True


def test_a_nit_pair_of_the_argus_readers_opens_check_f_and_shows_the_nit(svc):
    from router import patch_read_run as prr
    d = make(svc, read="ok", by_reader="argus")
    f = d / "patch_read_a1.json"
    rec = json.loads(f.read_text())
    rec["reader"]["id"] = prr.reader_id(prr.FIRST)
    rec["second"].update(verdict="concerns", severity="nit", note="year 0-99 is accepted")
    rec["second"]["reader"]["id"] = prr.reader_id(prr.SECOND)
    f.write_text(json.dumps(rec))
    status, c = get(svc)
    assert status == 200 and checks(c)["f"]["ok"] is True and "catatan kecil" in checks(c)["f"]["why"]
    assert c["patch_read"]["second"]["severity"] == "nit" and c["patch_read"]["second"]["verdict"] == "concerns"
    rec["second"]["severity"] = "blocker"                                                     # a blocker beside it closes the card again
    f.write_text(json.dumps(rec))
    assert checks(get(svc)[1])["f"]["ok"] is False
