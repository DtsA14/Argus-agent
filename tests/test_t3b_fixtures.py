"""SPEC_KARTU_SETUJU section 8, T3b: scripts/t3b_fixtures.py builds the planted-defect sets for the domain reader, keeps the key behind a hash printed first (in a
directory beside the jobs, not in them), records the readings through the real `examples-read` path and scores them (two readings of every set; all defects `concerns`
with the right reason; at most one good set flagged; the sets of real history present). No model, no Docker, no process: the readings here are written by the tests."""
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import t3b_fixtures as t3  # noqa: E402

from router import examples_read as er  # noqa: E402


@pytest.fixture
def built(tmp_path):
    root = tmp_path / "t3b"
    ids, h = t3.build(root, seed=1)
    return root, ids, h, json.loads((t3.keydir(root) / t3.KEY_FILE).read_text())["sets"]


def sha_of(root, jid):
    return t3.bundle(root, jid)[1]["bundle_sha256"]


def note_for(k, v):
    return f"the right number is {t3.NEED[k['set']][0]}" if k["kind"] == "defect" and v == "concerns" and k["set"] in t3.NEED else "checked"


def read_all(root, key, run, verdict_of, sources_of=None):
    for jid, k in key.items():
        v = verdict_of(k)
        writer_only = k["set"] == "d7" and v == "concerns"                  # the real path refuses an `ok` that rests on the writer's text alone
        src = sources_of(k, v) if sources_of else ["hanya tulisan penulis" if writer_only else "permintaan Atha"]
        t3.record(root, jid, run, sha_of(root, jid), v, src, note_for(k, v), "opus-test")


def right(k):
    return "concerns" if k["kind"] == "defect" else "ok"


def score(root, h, **kw):
    return t3.score(root, h, min_history=0, **kw)


def test_there_are_ten_defect_and_ten_good_sets_two_of_each_from_real_history_with_opaque_distinct_ids(built):
    root, ids, h, key = built
    kinds = [k["kind"] for k in key.values()]
    assert len(ids) == len(set(ids)) == 20 and set(ids) == set(key) and kinds.count("defect") == 10 and kinds.count("good") == 10
    assert sorted(k["set"] for k in key.values() if k["set"].startswith("h")) == ["h1", "h2"]
    assert not any(s in " ".join(ids) for s in ("defect", "good"))


def test_the_order_in_which_the_sets_are_shown_is_shuffled_by_the_seed(built):
    root, ids, h, key = built
    assert [key[j]["set"] for j in ids] != [spec[0] for spec in t3.SETS]


def test_the_key_and_the_readings_are_beside_the_jobs_not_in_them(built):
    root, ids, h, key = built
    assert t3.keydir(root) != root and not (root / t3.KEY_FILE).exists() and (t3.keydir(root) / t3.KEY_FILE).exists()
    read_all(root, key, 1, right)
    assert (t3.keydir(root) / t3.READS).exists() and not list(root.rglob(t3.READS)) and not list(root.rglob(t3.KEY_FILE))


def test_the_printed_hash_is_the_hash_of_the_key_and_score_needs_it(built):
    root, ids, h, key = built
    assert h == hashlib.sha256((t3.keydir(root) / t3.KEY_FILE).read_text().encode()).hexdigest()
    read_all(root, key, 1, right)
    read_all(root, key, 2, right)
    assert score(root, h)[0] is True
    ok, lines = score(root, "0" * 64)
    assert ok is False and "hash was printed" in lines[0]
    swapped = json.loads((t3.keydir(root) / t3.KEY_FILE).read_text())
    swapped["sets"][ids[0]]["kind"] = "good" if swapped["sets"][ids[0]]["kind"] == "defect" else "defect"
    (t3.keydir(root) / t3.KEY_FILE).write_text(json.dumps(swapped, sort_keys=True))
    assert score(root, h)[0] is False                                       # the key changed after the hash was printed


def test_a_reader_gets_the_template_and_one_bundle_and_nothing_about_the_key(built):
    root, ids, h, key = built
    for jid in ids:
        text, info = t3.bundle(root, jid)
        assert "You are the domain reader" in text
        low = text.lower()
        assert "defect set" not in low and key[jid]["set"] not in low.split() and "t3b" not in low and "planted" not in low
        assert info["template_sha256"] == er.TEMPLATE_SHA256
        for other in ids:
            if other != jid:
                assert other not in text


def test_every_bundle_carries_the_request_and_numbers_of_its_own_set_only(built):
    root, ids, h, key = built
    by = {key[j]["set"]: t3.bundle(root, j)[0] for j in ids}
    assert "Diskon member itu 3 persen" in by["d1"] and "percent = 30" in by["d1"] and "percent = 3\n" in by["g1"]
    assert "lot_size = 10\n" in by["d2"] and "lot_size = 100" in by["g2"]
    assert "Pembaca: angka sudah benar" in by["d8"] and "expect = 7.000.000" in by["d8"]          # d8's number is right: the sentence is its only defect
    assert "amount = 1.500.000" in by["g5"] and "unit = 1\n" in by["g5"]


def test_the_sets_are_in_a_separate_directory_and_never_in_the_live_one(tmp_path):
    with pytest.raises(SystemExit):
        t3.build(tmp_path / "pilot3a_live" / "jobs")
    full = tmp_path / "full"
    full.mkdir()
    (full / "x").write_text("x")
    with pytest.raises(SystemExit):
        t3.build(full)


def test_a_build_that_fails_halfway_leaves_nothing_and_can_be_run_again(tmp_path, monkeypatch):
    calls = []
    real = t3.write_job

    def flaky(jobs, jid, spec):
        calls.append(jid)
        if len(calls) == 3:
            raise RuntimeError("disk full")
        return real(jobs, jid, spec)
    monkeypatch.setattr(t3, "write_job", flaky)
    with pytest.raises(RuntimeError):
        t3.build(tmp_path / "t3b")
    assert not (tmp_path / "t3b").exists() and not t3.keydir(tmp_path / "t3b").exists()
    monkeypatch.setattr(t3, "write_job", real)
    assert len(t3.build(tmp_path / "t3b")[0]) == 20


def test_a_repo_that_does_not_exist_so_apply_would_refuse(built):
    root, ids, h, key = built
    assert all(json.loads((root / "jobs" / j / "job.json").read_text())["inputs"]["repo"] == "/nonexistent/t3b" for j in ids)


def test_a_recording_goes_through_the_real_path_with_the_sha_the_reader_saw(built):
    root, ids, h, key = built
    jid = ids[0]
    with pytest.raises(Exception, match="bundle"):
        t3.record(root, jid, 1, "0" * 64, "ok", ["permintaan Atha"], "fits", "opus-test")        # not the bundle that was shown
    assert not (t3.keydir(root) / t3.READS).exists()
    t3.record(root, jid, 1, sha_of(root, jid), "ok", ["permintaan Atha"], "fits", "opus-test")
    assert er.status(root / "jobs", jid, 1)[0] == "ok"
    (root / "jobs" / jid / "runs" / f"{jid}-w1" / "source" / "README.md").write_text("changed\n")
    assert er.status(root / "jobs", jid, 1)[0] == "stale"


def test_a_run_is_recorded_once(built):
    root, ids, h, key = built
    t3.record(root, ids[0], 1, sha_of(root, ids[0]), "ok", ["permintaan Atha"], "fits", "opus-test")
    with pytest.raises(SystemExit, match="already recorded"):
        t3.record(root, ids[0], 1, sha_of(root, ids[0]), "concerns", ["permintaan Atha"], "again", "opus-test")


def test_all_right_in_both_readings_passes_with_the_two_history_sets(built):
    root, ids, h, key = built
    read_all(root, key, 1, right)
    read_all(root, key, 2, right)
    ok, lines = t3.score(root, h)                                            # the default: two sets of real history are required, and they are there
    assert ok and lines[-1] == "PASS"


def test_fewer_history_sets_than_required_is_incomplete_not_a_pass(built):
    root, ids, h, key = built
    read_all(root, key, 1, right)
    read_all(root, key, 2, right)
    ok, lines = t3.score(root, h, min_history=3)
    assert ok is False and any("INCOMPLETE: 2 of 3" in l for l in lines) and "PASS" not in lines


def test_the_history_sets_carry_athenas_real_documents_the_real_signature_and_a_request_of_atha(built):
    root, ids, h, key = built
    by = {key[j]["set"]: t3.bundle(root, j)[0] for j in ids}
    assert "price floor Rp50" in by["h1"] and "price floor Rp50" in by["g9"]                       # athena's own CLAUDE.md is stale, as it really is
    assert "Harga minimum saham di BEI sekarang Rp1" in by["h1"] and "Kep-00157/BEI/10-2026" in by["h2"]
    assert "input slippage_buffer_pct = 0,15" in by["h2"] and "input slippage_buffer_pct = 0,07" in by["g10"]
    assert "call: risk_management.risk_manager.compute_position_size" in by["h1"] and "input entry_price = 50,0" in by["h1"]
    assert "expect blocked = ya (True)" in by["h1"] and "expect blocked = tidak (False)" in by["g9"] and "expect stop = 45,0" in by["g9"]
    assert all("shop.py" not in by[k] for k in ("h1", "h2", "g9", "g10"))


def test_the_numbers_of_the_history_sets_are_those_the_real_function_returned():
    # run once with athena's venv at 705db5b and at c82cd47 (see verification/t3b_history/risk_manager_stub.py); pinned here so they are not edited by accident
    by = {s[0]: s for s in t3.SETS}
    assert by["h1"][7][0]["expect"] == {"blocked": True, "stop": 50.0} and by["g9"][7][0]["expect"] == {"blocked": False, "stop": 45.0}
    assert by["h2"][7][0]["expect"] == {"sizing": 34.5, "original": 30.0} and by["g10"][7][0]["expect"] == {"sizing": 32.1, "original": 30.0}
    assert 1000.0 * 0 + 30.0 * 1.15 == pytest.approx(34.5) and 30.0 * 1.07 == pytest.approx(32.1)


@pytest.mark.parametrize("miss", ["d1", "d2", "d3", "d4", "d5", "d6", "d7", "d8", "h1", "h2"])
def test_one_missed_defect_in_either_reading_fails(built, miss):
    root, ids, h, key = built
    read_all(root, key, 1, right)
    read_all(root, key, 2, lambda k: "ok" if k["set"] == miss else right(k), lambda k, v: ["permintaan Atha"])
    ok, lines = score(root, h)
    assert ok is False and any(l.startswith(f"{miss} ") and "MISSED" in l for l in lines)


@pytest.mark.parametrize("miss", ["d1", "d2", "d3", "d4", "d5", "d6", "d7", "d8", "h1", "h2"])
def test_a_concerns_for_the_wrong_reason_is_not_a_catch(built, miss):
    root, ids, h, key = built
    for run in (1, 2):
        for jid, k in key.items():
            v = right(k)
            src = ["hanya tulisan penulis"] if k["set"] == "d7" and v == "concerns" else ["permintaan Atha"]
            note = "the Nothing else changes line looks odd" if k["set"] == miss and run == 2 else note_for(k, v)
            if k["set"] == miss and run == 2 and miss == "d7":
                src = ["permintaan Atha"]
            t3.record(root, jid, run, sha_of(root, jid), v, src, note, "opus-test")
    ok, lines = score(root, h)
    assert ok is False and any(l.startswith(f"{miss} ") and "MISSED" in l for l in lines)


def test_one_good_set_flagged_passes_and_two_fail(built):
    root, ids, h, key = built
    read_all(root, key, 1, lambda k: "concerns" if k["set"] == "g7" else right(k))
    read_all(root, key, 2, right)
    assert score(root, h)[0] is True
    root2 = root.parent / "t3b2"
    ids2, h2 = t3.build(root2, seed=2)
    key2 = json.loads((t3.keydir(root2) / t3.KEY_FILE).read_text())["sets"]
    read_all(root2, key2, 1, lambda k: "concerns" if k["set"] in ("g7", "g8") else right(k))
    read_all(root2, key2, 2, right)
    assert score(root2, h2)[0] is False


def test_flagging_everything_is_not_a_pass(built):
    root, ids, h, key = built
    read_all(root, key, 1, lambda k: "concerns")
    read_all(root, key, 2, lambda k: "concerns")
    assert score(root, h)[0] is False


def test_a_set_read_only_once_is_not_scored_as_passed(built):
    root, ids, h, key = built
    read_all(root, key, 1, right)
    ok, lines = score(root, h)
    assert ok is False and any("needs two readings" in l for l in lines)


def test_the_first_reading_of_a_run_is_the_one_that_counts_and_a_second_is_refused(built):
    root, ids, h, key = built
    d7 = [j for j, k in key.items() if k["set"] == "d7"][0]
    read_all(root, key, 1, right)
    for jid, k in key.items():
        t3.record(root, jid, 2, sha_of(root, jid), right(k) if jid != d7 else "ok", ["permintaan Atha"], note_for(k, right(k)), "opus-test")
    assert score(root, h)[0] is False
    with pytest.raises(SystemExit):
        t3.record(root, d7, 2, sha_of(root, d7), "concerns", ["hanya tulisan penulis"], "hanya tulisan penulis", "opus-test")
    assert score(root, h)[0] is False


def test_the_note_is_compared_without_case_and_without_thousands_dots(built):
    root, ids, h, key = built
    d1 = [j for j, k in key.items() if k["set"] == "d1"][0]
    for run in (1, 2):
        for jid, k in key.items():
            t3.record(root, jid, run, sha_of(root, jid), right(k), ["hanya tulisan penulis" if k["set"] == "d7" and right(k) == "concerns" else "permintaan Atha"],
                      "THE PRICE SHOULD BE 194.000" if jid == d1 else note_for(k, right(k)), "opus-test")
    assert score(root, h)[0] is True


def test_a_number_that_only_contains_the_right_one_is_not_the_right_reason(built):
    root, ids, h, key = built
    d2 = [j for j, k in key.items() if k["set"] == "d2"][0]
    for run in (1, 2):
        for jid, k in key.items():
            t3.record(root, jid, run, sha_of(root, jid), right(k), ["hanya tulisan penulis" if k["set"] == "d7" and right(k) == "concerns" else "permintaan Atha"],
                      "the answer should be 1000 lot" if jid == d2 else note_for(k, right(k)), "opus-test")
    ok, lines = score(root, h)
    assert ok is False and any(l.startswith("d2 ") and "MISSED" in l for l in lines)


def test_the_hash_file_is_not_needed_the_printed_hash_is_the_proof(built):
    root, ids, h, key = built
    assert not list(t3.keydir(root).glob("*.sha256")) and len(h) == 64


def test_the_history_sets_state_the_request_the_capital_and_the_signature_the_card_needs(built):
    root, ids, h, key = built
    by = {key[j]["set"]: (j, t3.bundle(root, j)[0]) for j in ids}
    assert "ARB 7% untuk saham harga di atas Rp10" in by["h2"][1] and "input capital_idr = 1.000.000.000" in by["h1"][1]
    stub = root / "jobs" / by["h1"][0] / "runs" / f"{by['h1'][0]}-w1" / "source" / "risk_management" / "risk_manager.py"
    assert "def compute_position_size(" in stub.read_text() and "slippage_buffer_pct" in stub.read_text()
    assert not (root / "jobs" / by["d1"][0] / "runs" / f"{by['d1'][0]}-w1" / "source" / "risk_management").exists()      # the invented sets keep their small shop


def test_the_right_reason_of_the_arb_set_is_7_percent_not_15(built):
    root, ids, h, key = built
    h2 = [j for j, k in key.items() if k["set"] == "h2"][0]
    for run, note in ((1, "the buffer should be 7% per the request, not 15%"), (2, "the buffer should be 7 persen")):
        for jid, k in key.items():
            t3.record(root, jid, run, sha_of(root, jid), right(k), ["hanya tulisan penulis" if k["set"] == "d7" and right(k) == "concerns" else "permintaan Atha"],
                      note if jid == h2 else note_for(k, right(k)), "opus-test")
    assert score(root, h)[0] is True
    root2 = root.parent / "t3b_c"
    ids2, h2h = t3.build(root2, seed=1)
    key2 = json.loads((t3.keydir(root2) / t3.KEY_FILE).read_text())["sets"]
    only15 = [j for j, k in key2.items() if k["set"] == "h2"][0]
    for run in (1, 2):
        for jid, k in key2.items():
            t3.record(root2, jid, run, sha_of(root2, jid), right(k), ["hanya tulisan penulis" if k["set"] == "d7" and right(k) == "concerns" else "permintaan Atha"],
                      "the buffer of 15% is odd" if jid == only15 else note_for(k, right(k)), "opus-test")
    ok, lines = score(root2, h2h)
    assert ok is False and any(l.startswith("h2 ") and "MISSED" in l for l in lines)


def test_without_history_sets_in_the_key_the_score_is_incomplete(built):
    root, ids, h, key = built
    read_all(root, key, 1, right)
    read_all(root, key, 2, right)
    body = json.loads((t3.keydir(root) / t3.KEY_FILE).read_text())
    body["sets"] = {j: v for j, v in body["sets"].items() if not v["set"].startswith("h")}
    text = json.dumps(body, sort_keys=True)
    (t3.keydir(root) / t3.KEY_FILE).write_text(text)
    import hashlib
    ok, lines = t3.score(root, hashlib.sha256(text.encode()).hexdigest())
    assert ok is False and any("INCOMPLETE: 0 of 2" in l for l in lines)


def test_the_history_sets_carry_the_draft_domain_document_first_and_the_invented_sets_do_not(built):
    root, ids, h, key = built
    by = {key[j]["set"]: t3.bundle(root, j)[0] for j in ids}
    for k in ("h1", "h2", "g9", "g10"):
        assert "=== DATA repo doc: DOMAIN.md ===" in by[k] and by[k].index("repo doc: DOMAIN.md") < by[k].index("repo doc: README.md")
        assert "Jarak stop dasar = 1,5 x ATR" in by[k] and "DRAFT ditulis Claude" in by[k]
    assert "repo doc: DOMAIN.md" not in by["d1"] and "repo doc: DOMAIN.md" not in by["g1"]
    assert "price floor Rp50" in by["h1"]                                                      # athena's own stale CLAUDE.md is still there, after the domain document


def test_the_rules_of_the_draft_domain_document_give_the_numbers_of_the_four_history_sets():
    import math
    text = (t3.HISTORY / "athena" / "DOMAIN.md").read_text()
    for needle in ("tick Rp1", "Rp1** sejak 28 September 2026", "1,5 x ATR", "dibulatkan ke BAWAH ke tick", "30 x 1,15 = 34,5", "30 x 1,07 = 32,1", "1 lot = 100 lembar"):
        assert needle in text
    stop = math.floor((50 - 1.5 * 3) / 1) * 1                                                  # g9: entry 50, ATR 3, tick Rp1
    assert stop == 45 and 1000 - 1.5 * 20 == 970 and 30 * 1.15 == pytest.approx(34.5) and 30 * 1.07 == pytest.approx(32.1)
