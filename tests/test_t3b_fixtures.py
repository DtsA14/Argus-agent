"""SPEC_KARTU_SETUJU section 8, T3b: scripts/t3b_fixtures.py builds the planted-defect sets for the domain reader, hides the key behind a hash printed first,
records the readings through the real `examples-read` path and scores them (two readings of every set; all defects `concerns`; at most one good set flagged).
No model, no Docker, no process: the readings here are written by the tests."""
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
    return root, ids, h, json.loads((root / t3.KEY_FILE).read_text())["sets"]


def read_all(root, key, run, verdict_of):
    for jid, k in key.items():
        v = verdict_of(k)
        writer_only = k["set"] == "d7" and v == "concerns"                  # the real path refuses an `ok` that rests on the writer's text alone
        t3.record(root, jid, run, v, ["hanya tulisan penulis" if writer_only else "permintaan Atha"], "checked", "opus-test")


def right(k):
    return "concerns" if k["kind"] == "defect" else "ok"


def test_there_are_eight_defect_and_eight_good_sets_with_opaque_distinct_ids(built):
    root, ids, h, key = built
    assert len(ids) == len(set(ids)) == 16 and set(ids) == set(key)
    assert sorted(k["kind"] for k in key.values()).count("defect") == 8 and sorted(k["kind"] for k in key.values()).count("good") == 8
    assert not any(s in " ".join(ids) for s in ("defect", "good"))


def test_the_order_in_which_the_sets_are_shown_is_shuffled_by_the_seed(built):
    root, ids, h, key = built
    assert [key[j]["set"] for j in ids] != [spec[0] for spec in t3.SETS]


def test_the_key_hash_is_printed_and_the_file_is_checked_against_it_before_scoring(built):
    root, ids, h, key = built
    assert h == hashlib.sha256((root / t3.KEY_FILE).read_text().encode()).hexdigest() == (root / t3.KEY_HASH).read_text().strip()
    read_all(root, key, 1, right)
    read_all(root, key, 2, right)
    assert t3.score(root)[0] is True
    swapped = json.loads((root / t3.KEY_FILE).read_text())
    swapped["sets"][ids[0]]["kind"] = "good" if swapped["sets"][ids[0]]["kind"] == "defect" else "defect"
    (root / t3.KEY_FILE).write_text(json.dumps(swapped, sort_keys=True))
    ok, lines = t3.score(root)
    assert ok is False and "hash was printed" in lines[0]


def test_a_reader_gets_the_template_and_one_bundle_and_nothing_about_the_key(built):
    root, ids, h, key = built
    for jid in ids:
        text, info = t3.bundle(root, jid)
        assert er.TEMPLATE.strip() in text or "You are the domain reader" in text
        low = text.lower()
        assert "defect set" not in low and key[jid]["set"] not in low.split() and "t3b" not in low and "planted" not in low
        assert info["template_sha256"] == er.TEMPLATE_SHA256
        for other in ids:
            if other != jid:
                assert other not in text


def test_every_bundle_carries_the_request_and_numbers_of_its_own_set_only(built):
    root, ids, h, key = built
    texts = {jid: t3.bundle(root, jid)[0] for jid in ids}
    by = {key[j]["set"]: texts[j] for j in ids}
    assert "Diskon member itu 3 persen" in by["d1"] and "percent = 30" in by["d1"] and "percent = 3\n" in by["g1"]
    assert "lot_size = 10\n" in by["d2"] and "lot_size = 100" in by["g2"]
    assert "Pembaca: angka sudah benar" in by["d8"] and "hanya" not in by["d8"].split("=== DATA request")[1].split("===")[0]


def test_the_sets_are_in_a_separate_directory_and_never_in_the_live_one(tmp_path):
    with pytest.raises(SystemExit):
        t3.build(tmp_path / "pilot3a_live" / "jobs")
    full = tmp_path / "full"
    full.mkdir()
    (full / "x").write_text("x")
    with pytest.raises(SystemExit):
        t3.build(full)


def test_a_repo_that_does_not_exist_so_apply_would_refuse(built):
    root, ids, h, key = built
    assert all(json.loads((root / "jobs" / j / "job.json").read_text())["inputs"]["repo"] == "/nonexistent/t3b" for j in ids)


def test_a_recording_goes_through_the_real_path_and_a_stale_bundle_is_refused(built):
    root, ids, h, key = built
    jid = ids[0]
    t3.record(root, jid, 1, "ok", ["permintaan Atha"], "fits", "opus-test")
    kind, rec = er.status(root / "jobs", jid, 1)
    assert kind == "ok" and rec["reader"]["id"] == "opus-test" if isinstance(rec["reader"], dict) else kind == "ok"
    (root / "jobs" / jid / "runs" / f"{jid}-w1" / "source" / "README.md").write_text("changed\n")
    assert er.status(root / "jobs", jid, 1)[0] == "stale"


def test_all_right_in_both_readings_passes(built):
    root, ids, h, key = built
    read_all(root, key, 1, right)
    read_all(root, key, 2, right)
    ok, lines = t3.score(root)
    assert ok and lines[-1].endswith("PASS")


@pytest.mark.parametrize("miss", ["d1", "d2", "d3", "d4", "d5", "d6", "d7", "d8"])
def test_one_missed_defect_in_either_reading_fails(built, miss):
    root, ids, h, key = built
    read_all(root, key, 1, right)
    read_all(root, key, 2, lambda k: "ok" if k["set"] == miss else right(k))
    ok, lines = t3.score(root)
    assert ok is False and any(l.startswith(f"{miss} ") and "MISSED" in l for l in lines)


def test_one_good_set_flagged_passes_and_two_fail(built):
    root, ids, h, key = built
    read_all(root, key, 1, lambda k: "concerns" if k["set"] == "g7" else right(k))
    read_all(root, key, 2, right)
    assert t3.score(root)[0] is True
    root2 = root.parent / "t3b2"
    ids2, _ = t3.build(root2, seed=2)
    key2 = json.loads((root2 / t3.KEY_FILE).read_text())["sets"]
    read_all(root2, key2, 1, lambda k: "concerns" if k["set"] in ("g7", "g8") else right(k))
    read_all(root2, key2, 2, right)
    assert t3.score(root2)[0] is False


def test_flagging_everything_is_not_a_pass(built):
    root, ids, h, key = built
    read_all(root, key, 1, lambda k: "concerns")
    read_all(root, key, 2, lambda k: "concerns")
    assert t3.score(root)[0] is False


def test_a_set_read_only_once_is_not_scored_as_passed(built):
    root, ids, h, key = built
    read_all(root, key, 1, right)
    ok, lines = t3.score(root)
    assert ok is False and any("needs two readings" in l for l in lines)


def test_the_rule_only_the_writer_states_must_be_named_as_such(built):
    root, ids, h, key = built
    d7 = [j for j, k in key.items() if k["set"] == "d7"][0]
    for run in (1, 2):
        for jid, k in key.items():
            if jid == d7:
                t3.record(root, jid, run, "concerns", ["permintaan Atha"], "something is off", "opus-test")
            else:
                t3.record(root, jid, run, right(k), ["permintaan Atha"], "checked", "opus-test")
    ok, lines = t3.score(root)
    assert ok is False and any(l.startswith("d7 ") and "MISSED" in l for l in lines)
    t3.record(root, d7, 1, "concerns", ["hanya tulisan penulis"], "rounding rule only in the PRD", "opus-test")
    t3.record(root, d7, 2, "concerns", ["hanya tulisan penulis"], "rounding rule only in the PRD", "opus-test")
    assert t3.score(root)[0] is False                                   # the first (wrong) readings of each run are still on record
