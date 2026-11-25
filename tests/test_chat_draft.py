"""SPEC_CHAT_UI3D: `GET /api/draft/<job>`, the detail of a job's last draft: the existing tests it changes as a diff against the intake's frozen copy. Real files, a real server."""
import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_chat as read_only  # noqa: E402
import test_chat_t4b as t4  # noqa: E402
from router import job as rj  # noqa: E402

svc = t4.svc
J = t4.J1
OLD = "def test_x():\n    assert total([1]) == 1\n\n\ndef test_y():\n    assert total([]) == 0\n"
NEW = "def test_x():\n    assert total([1]) == 1\n\n\ndef test_y():\n    assert total([]) == 0\n\n\ndef test_z():\n    assert total([2, 3]) == 5\n"
PATH = "tests/test_a.py"


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def make(svc, changed=None, old=OLD, report=True, source=True, **draft_kw):
    ct = changed if changed is not None else [{"path": PATH, "content": NEW, "removed": [{"node": "test_old", "reason": "no longer true"}],
                                                "modified": [{"node": "test_y", "reason": "the floor moved"}]}]
    d = t4.rich(**draft_kw)
    d["changed_tests"] = ct
    jd = t4.awaiting(svc, J, t4.TEXT, d=d)
    run = jd / "runs" / "d1-run"
    if source and old is not None:
        (run / "source" / "tests").mkdir(parents=True)
        (run / "source" / PATH).write_text(old)
    if report:
        rep = {"draft_sha256": rj.draft_sha_of(d), "changed": {PATH: {"before": sha(old if old is not None else ""), "after": sha(NEW)}},
               "baseline": {"v1": {"must_pass": {}}}}
        (run / "check_report.json").write_text(json.dumps(rep))
    return jd


def detail(s, job=J):
    return s.request("GET", f"/api/draft/{job}")


def test_a_draft_that_changes_an_old_test_shows_the_diff_the_hash_check_and_the_writers_notes(svc):
    make(svc)
    st, d = detail(svc)
    assert st == 200 and d["job"] == J and len(d["draft_sha"]) == 64 and d["draft_sha12"] == d["draft_sha"][:12]
    assert d["writable"] == ["src/a.py", "tests/test_a.py"] and d["must_pass"] == ["tests/test_a.py::test_x"] and d["tests_n"] == 1
    tst = d["tests"][0]
    assert tst["path"] == PATH and tst["before_verified"] is True and tst["note"] is None
    lines = tst["diff"].splitlines()
    assert lines[0] == f"--- a/{PATH}" and lines[1] == f"+++ b/{PATH}" and "+def test_z():" in lines and "+    assert total([2, 3]) == 5" in lines
    assert not any(ln.startswith("-") and not ln.startswith("---") for ln in lines)                     # an append removes nothing
    assert tst["removed"] == [{"node": "test_old", "reason": "no longer true"}] and tst["modified"] == [{"node": "test_y", "reason": "the floor moved"}]


def test_a_removed_line_shows_as_a_minus_line(svc):
    make(svc, changed=[{"path": PATH, "content": "def test_x():\n    assert True\n"}])
    diff = detail(svc)[1]["tests"][0]["diff"]
    assert "-    assert total([1]) == 1" in diff.splitlines() and "+    assert True" in diff.splitlines()


def test_the_plan_and_the_writers_notes_come_with_it_when_the_report_is_this_drafts(svc):
    make(svc)
    d = detail(svc)[1]
    assert d["plan"]["steps"] == ["do the thing"] and d["plan"]["risks"] == ["it may break b"] and d["unverifiable"] == ["the page stays unchanged"] and "summary_note" not in d


def test_a_missing_or_foreign_report_still_shows_the_diff_but_says_the_old_text_is_not_verified(svc):
    make(svc, report=False)
    d = detail(svc)[1]
    assert d["tests"][0]["before_verified"] is False and d["tests"][0]["diff"] and d["summary_note"] == "summary unavailable"


def test_an_old_text_that_changed_after_the_report_is_not_verified(svc):
    jd = make(svc)
    (jd / "runs" / "d1-run" / "source" / PATH).write_text(OLD + "# edited\n")
    assert detail(svc)[1]["tests"][0]["before_verified"] is False


def test_a_missing_old_file_is_unavailable_for_that_test_only(svc):
    make(svc, source=False)
    d = detail(svc)[1]
    assert d["tests"][0]["diff"] is None and d["tests"][0]["note"] == "unavailable" and d["writable"]


def test_an_old_file_that_is_a_link_is_not_followed(svc, tmp_path):
    jd = make(svc)
    secret = tmp_path / "secret.txt"
    secret.write_text("TOP SECRET LINE\n")
    src = jd / "runs" / "d1-run" / "source" / PATH
    src.unlink()
    src.symlink_to(secret)
    raw = json.dumps(detail(svc)[1])
    assert "TOP SECRET" not in raw and detail(svc)[1]["tests"][0]["diff"] is None


def test_a_source_directory_that_is_a_link_is_not_followed(svc, tmp_path):
    jd = make(svc)
    outside = tmp_path / "outside"
    (outside / "tests").mkdir(parents=True)
    (outside / PATH).write_text("OUTSIDE\n")
    import shutil
    shutil.rmtree(jd / "runs" / "d1-run" / "source")
    (jd / "runs" / "d1-run" / "source").symlink_to(outside)
    d = detail(svc)[1]
    assert "OUTSIDE" not in json.dumps(d) and d["tests"][0]["diff"] is None


@pytest.mark.parametrize("bad", ["../x.py", "/etc/passwd", "tests/../../x", "a b.py", "tests/\x00x.py", "", ".hidden", "a" * 300, 3, None, ["x"]])
def test_a_path_that_is_not_a_plain_relative_path_is_not_read_or_shown(svc, bad):
    make(svc, changed=[{"path": bad, "content": NEW}])
    d = detail(svc)[1]
    assert d["tests"][0]["path"] is None and d["tests"][0]["diff"] is None and d["tests"][0]["note"] == "the path is not shown"


def test_a_new_text_over_the_limit_gets_no_diff(svc):
    make(svc, changed=[{"path": PATH, "content": "x\n" * (200 * 1024)}])
    d = detail(svc)[1]["tests"][0]
    assert d["diff"] is None and d["note"] == "the new text is too large to show" and d["path"] == PATH


def test_a_text_that_looks_like_a_key_is_withheld_by_the_scrubber_not_shown(svc):
    make(svc, changed=[{"path": PATH, "content": OLD + '\nTOKEN = "sk-ant-api03-abcdefghijklmnop"\n'}])
    raw = json.dumps(detail(svc)[1])
    assert "sk-ant-api03" not in raw


def test_only_the_first_files_are_shown_and_the_count_is_told(svc):
    make(svc, changed=[{"path": f"tests/test_{n}.py", "content": NEW} for n in range(8)])
    d = detail(svc)[1]
    assert d["tests_n"] == 8 and len(d["tests"]) == 5


@pytest.mark.parametrize("junk", ["text", 5, {"a": 1}, [None, 3, "x", []], [{"path": PATH, "content": 7}], [{"path": PATH, "content": NEW, "removed": "x", "modified": 4}]])
def test_a_hostile_changed_tests_field_never_takes_the_page_away(svc, junk):
    make(svc, changed=junk)
    st, d = detail(svc)
    assert st == 200 and d["writable"] == ["src/a.py", "tests/test_a.py"]


def test_the_notes_are_scrubbed_and_cut(svc):
    make(svc, changed=[{"path": PATH, "content": NEW, "removed": [{"node": "n" * 400, "reason": "r‮" + "x" * 900}], "modified": [{"node": 3, "reason": None}] * 80}])
    t = detail(svc)[1]["tests"][0]
    assert len(t["removed"][0]["node"]) == 200 and len(t["removed"][0]["reason"]) <= 500 and "‮" not in t["removed"][0]["reason"] and len(t["modified"]) == 50


def test_no_draft_a_bad_id_and_a_linked_job_directory_are_a_404(svc, tmp_path):
    assert detail(svc, J)[0] == 404                                                   # no such job
    assert detail(svc, "j20261117_110000_BAD1")[0] == 404 and detail(svc, "nope")[0] == 404
    make(svc)
    real = svc.jobs / J
    moved = tmp_path / "elsewhere"
    real.rename(moved)
    real.symlink_to(moved)
    assert detail(svc)[0] == 404


def test_a_draft_reached_through_a_link_is_a_404(svc, tmp_path):
    jd = make(svc)
    run = jd / "runs" / "d1-run"
    (tmp_path / "other").mkdir()
    (tmp_path / "other" / "draft.json").write_text((run / "draft.json").read_text())
    (run / "draft.json").unlink()
    (run / "draft.json").symlink_to(tmp_path / "other" / "draft.json")
    assert detail(svc)[0] == 404


def test_no_path_of_the_repository_and_nothing_else_travels(svc):
    make(svc)
    raw = json.dumps(detail(svc)[1])
    assert "/secret/path" not in raw and str(svc.jobs) not in raw
    assert set(detail(svc)[1]) <= {"job", "draft_sha", "draft_sha12", "state", "writable", "must_pass", "tests", "tests_n", "plan", "warnings", "unverifiable", "baseline_note", "summary_note"}


def test_the_route_needs_the_chat_actions_and_is_not_a_write(svc):
    ro = read_only.Service(svc.jobs)
    try:
        assert ro.request("GET", f"/api/draft/{J}")[0] == 404
    finally:
        ro.stop()
    st = svc.request("POST", f"/api/draft/{J}", body={})[0]
    assert st in (400, 403, 404, 405, 421)


def test_it_reads_a_draft_that_is_already_approved_too(svc):
    jd = make(svc)
    p = jd / "job.json"
    data = json.loads(p.read_text())
    data["state"] = "REVIEW_READY"
    p.write_text(json.dumps(data))
    st, d = detail(svc)
    assert st == 200 and d["state"] == "REVIEW_READY" and d["tests"][0]["diff"]
