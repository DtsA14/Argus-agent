"""SPEC_OLD_TEST_LEAKS: old tests that will break with the new behaviour are pointed out before approve."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_drafter as tdr  # noqa: E402
from acceptance import leaks as lk  # noqa: E402
from codetask import drafter as dt  # noqa: E402
from router import job as rj  # noqa: E402

ISSUE = 'Add "max_usd" to the job answer, right after "cost_usd".'
OLD_KEYS = ["job", "state", "created_at", "cost_usd", "running"]
NEW_KEYS = ["job", "state", "created_at", "cost_usd", "max_usd", "running"]


def lst(keys):
    return "KEYS = [" + ", ".join(repr(k) for k in keys) + "]\n"


def dct(keys):
    return "EXPECTED = {" + ", ".join(f"{k!r}: 1" for k in keys) + "}\n"


def base(tmp_path, files):
    for rel, text in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(text, bytes):
            p.write_bytes(text)
        else:
            p.write_text(text, encoding="utf-8")
    return tmp_path


def draft(new=None, changed=None):
    return {"new_tests": [{"path": "tests/test_new.py", "content": c} for c in [new or lst(NEW_KEYS)]],
            "changed_tests": [{"path": p, "content": c} for p, c in (changed or {}).items()]}


@pytest.mark.parametrize("shape", [lst, dct])
def test_an_old_test_with_the_new_shape_minus_a_key_the_issue_names_is_flagged(tmp_path, shape):
    d = base(tmp_path, {"tests/test_old.py": "\n\n" + shape(OLD_KEYS)})
    (hit,) = lk.find(d, draft(new=shape(NEW_KEYS)), ISSUE)
    assert hit["path"] == "tests/test_old.py" and hit["added"] == ["max_usd"] and hit["line"] == 3
    assert hit["kind"] == ("list" if shape is lst else "dict")


def test_a_list_in_the_new_test_matches_a_dict_in_the_old_one(tmp_path):
    d = base(tmp_path, {"tests/test_old.py": dct(OLD_KEYS)})
    assert [h["path"] for h in lk.find(d, draft(), ISSUE)] == ["tests/test_old.py"]


def test_the_key_must_be_named_in_the_issue(tmp_path):
    d = base(tmp_path, {"tests/test_old.py": lst(OLD_KEYS)})
    assert lk.find(d, draft(), "Make the answer carry the cap.") == []
    assert lk.find(d, draft(), 'the key "max_usd_total" is new') == []          # a whole word, not a prefix


def test_more_than_two_added_keys_are_not_a_leak(tmp_path):
    d = base(tmp_path, {"tests/test_old.py": lst(OLD_KEYS)})
    new = lst(OLD_KEYS + ["a_key", "b_key", "c_key"])
    assert lk.find(d, draft(new=new), "a_key b_key c_key") == []
    assert [h["path"] for h in lk.find(d, draft(new=lst(OLD_KEYS + ["a_key", "b_key"])), "a_key b_key")] == \
        ["tests/test_old.py"]


def test_a_short_or_equal_or_unrelated_set_is_not_a_leak(tmp_path):
    short = ["job", "state", "created_at"]
    d = base(tmp_path, {"tests/test_short.py": lst(short), "tests/test_same.py": lst(NEW_KEYS),
                        "tests/test_other.py": lst(["x1", "x2", "x3", "x4"])})
    assert lk.find(d, draft(new=lst(short + ["max_usd"])), ISSUE) == []          # |O| < 4
    assert lk.find(d, draft(), ISSUE) == []                                       # O == N, and O not a subset of N


def test_a_file_the_draft_changes_is_not_flagged_and_a_non_test_is_not_scanned(tmp_path):
    d = base(tmp_path, {"tests/test_old.py": lst(OLD_KEYS), "src/x.py": lst(OLD_KEYS)})
    assert lk.find(d, draft(changed={"tests/test_old.py": lst(NEW_KEYS)}), ISSUE) == []


def test_an_unparsable_or_huge_old_file_is_skipped(tmp_path, monkeypatch):
    d = base(tmp_path, {"tests/test_bad.py": "def (:\n", "tests/test_bin.py": b"\xff\xfe\x00",
                        "tests/test_big.py": lst(OLD_KEYS)})
    monkeypatch.setattr(lk, "MAX_BYTES", 20)
    assert lk.find(d, draft(), ISSUE) == []


def test_a_draft_test_that_does_not_parse_has_no_sets_and_no_error(tmp_path):
    d = base(tmp_path, {"tests/test_old.py": lst(OLD_KEYS)})
    assert lk.find(d, draft(new="def (:\n"), ISSUE) == []


def test_at_most_twenty_files_are_reported_in_path_order(tmp_path):
    d = base(tmp_path, {f"tests/test_{i:02d}.py": lst(OLD_KEYS) for i in range(25)})
    found = lk.find(d, draft(), ISSUE)
    assert [h["path"] for h in found] == [f"tests/test_{i:02d}.py" for i in range(20)]


# ---- where it shows ------------------------------------------------------------------------------------------------

HIT = {"path": "tests/test_old.py", "line": 3, "kind": "list", "added": ["max_usd"]}


def review(report):
    drafted, _ = dt.draft_from_args(dict(tdr.ARGS), base="shop", policy=tdr.POLICY)
    state = {"status": dt.DRAFTED, "draft": drafted, "report": report, "drafting": {}}
    return dt.review_text("d1", {"intake": "shop", "issue": ISSUE}, state,
                          {"usd": 0.01, "usd_complete": True, "calls": 1})


def test_the_review_lists_the_old_tests_that_may_break_with_what_to_do():
    text = review({"leaks": [HIT]})
    assert "## Old tests that may break" in text
    assert "`tests/test_old.py` line 3 (list): the new tests expect it plus `max_usd`" in text
    assert "add them to changed_tests" in text


def test_the_review_says_when_nothing_looks_affected():
    assert "No old test looks affected" in review({"leaks": []})
    assert "## Old tests that may break" not in review({"leaks": []})


def test_the_approve_screen_line_comes_from_the_intake_not_the_report(tmp_path, monkeypatch):
    root = tmp_path
    base(root / "fixtures" / "repos" / "shop", {"tests/test_old.py": lst(OLD_KEYS)})
    job = SimpleNamespace(root=root, data={"inputs": {"issue": ISSUE}})
    line = ("old tests that may break (not changed by the draft): tests/test_old.py: read DRAFT_REVIEW.md")
    d = {**draft(), "base": "shop"}
    assert rj.leak_lines(job, d) == [line]
    assert rj.leak_lines(job, {**draft(changed={"tests/test_old.py": lst(NEW_KEYS)}), "base": "shop"}) == []
    assert rj.leak_lines(SimpleNamespace(root=root, data={"inputs": {"issue": "nothing"}}), d) == []
