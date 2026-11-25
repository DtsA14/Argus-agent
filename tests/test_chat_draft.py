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
RUN = f"{J}-d1"                                                                  # the run id a harness job has: the job id and the stage name


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def make(svc, changed=None, old=OLD, report=True, source=True, **draft_kw):
    ct = changed if changed is not None else [{"path": PATH, "content": NEW, "removed": [{"node": "test_old", "reason": "no longer true"}],
                                                "modified": [{"node": "test_y", "reason": "the floor moved"}]}]
    d = t4.rich(**draft_kw)
    d["changed_tests"] = ct
    jd = t4.awaiting(svc, J, t4.TEXT, d=d)
    os.rename(jd / "runs" / "d1-run", jd / "runs" / RUN)
    data = json.loads((jd / "job.json").read_text())
    data["stages"]["d1"]["run_id"] = RUN
    (jd / "job.json").write_text(json.dumps(data))
    run = jd / "runs" / RUN
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
    assert tst["path"] == PATH and tst["before"] == "matches" and tst["note"] is None
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
    assert d["tests"][0]["before"] == "no_record" and d["tests"][0]["diff"] and d["summary_note"] == "summary unavailable"


def test_an_old_text_that_changed_after_the_report_differs_from_the_recorded_hash(svc):
    jd = make(svc)
    (jd / "runs" / RUN / "source" / PATH).write_text(OLD + "# edited\n")
    assert detail(svc)[1]["tests"][0]["before"] == "differs"                                 # a hash was recorded and the copy does not match it: not the same as "no record"


def test_a_missing_old_file_is_unavailable_for_that_test_only(svc):
    make(svc, source=False)
    d = detail(svc)[1]
    assert d["tests"][0]["diff"] is None and d["tests"][0]["note"] == "unavailable" and d["writable"]


def test_an_old_file_that_is_a_link_is_not_followed(svc, tmp_path):
    jd = make(svc)
    secret = tmp_path / "secret.txt"
    secret.write_text("TOP SECRET LINE\n")
    src = jd / "runs" / RUN / "source" / PATH
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
    shutil.rmtree(jd / "runs" / RUN / "source")
    (jd / "runs" / RUN / "source").symlink_to(outside)
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
    run = jd / "runs" / RUN
    (tmp_path / "other").mkdir()
    (tmp_path / "other" / "draft.json").write_text((run / "draft.json").read_text())
    (run / "draft.json").unlink()
    (run / "draft.json").symlink_to(tmp_path / "other" / "draft.json")
    assert detail(svc)[0] == 404


def test_no_path_of_the_repository_and_nothing_else_travels(svc):
    make(svc)
    raw = json.dumps(detail(svc)[1])
    assert "/secret/path" not in raw and str(svc.jobs) not in raw
    assert set(detail(svc)[1]) <= {"job", "draft_sha", "draft_sha12", "state", "writable", "must_pass", "tests", "tests_n", "tests_ok", "plan", "warnings", "unverifiable", "baseline_note", "summary_note"}


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


# ---- the second review ---------------------------------------------------------------------------------------------------------------------

def test_a_report_of_another_draft_gives_no_record_even_when_its_hash_would_match(svc):
    jd = make(svc)
    p = jd / "runs" / RUN / "check_report.json"
    rep = json.loads(p.read_text())
    rep["draft_sha256"] = "f" * 64
    p.write_text(json.dumps(rep))
    assert detail(svc)[1]["tests"][0]["before"] == "no_record"


def test_a_report_without_an_entry_for_the_file_gives_no_record(svc):
    jd = make(svc)
    p = jd / "runs" / RUN / "check_report.json"
    rep = json.loads(p.read_text())
    rep["changed"] = {}
    p.write_text(json.dumps(rep))
    assert detail(svc)[1]["tests"][0]["before"] == "no_record"


def test_a_directory_in_the_middle_of_the_path_that_is_a_link_is_not_followed(svc, tmp_path):
    import shutil
    jd = make(svc)
    outside = tmp_path / "outside_tests"
    outside.mkdir()
    (outside / "test_a.py").write_text("OUTSIDE MIDDLE\n")
    shutil.rmtree(jd / "runs" / RUN / "source" / "tests")
    (jd / "runs" / RUN / "source" / "tests").symlink_to(outside)
    d = detail(svc)[1]
    assert "OUTSIDE MIDDLE" not in json.dumps(d) and d["tests"][0]["diff"] is None and d["tests"][0]["note"] == "unavailable"


def test_an_old_file_over_the_limit_gets_no_diff_and_is_unavailable(svc):
    jd = make(svc)
    (jd / "runs" / RUN / "source" / PATH).write_text("y\n" * (200 * 1024))
    d = detail(svc)[1]["tests"][0]
    assert d["diff"] is None and d["note"] == "unavailable"


def test_a_key_that_is_only_in_the_old_text_is_withheld_too(svc):
    make(svc, old=OLD + 'TOKEN = "sk-ant-api03-abcdefghijklmnop"\n')
    raw = json.dumps(detail(svc)[1])
    assert "sk-ant-api03" not in raw


@pytest.mark.parametrize("bad", ["/etc", "/", "../x", "x", "j20261117_110000_aaa1-d1/..", "j20261117_110000_aaa1-d1/x", "j20261117_110000_aaa1-", 5, None, "other-d1"])
def test_a_run_id_that_is_not_this_jobs_run_shape_is_a_404_and_nothing_is_read(svc, bad):
    jd = make(svc)
    data = json.loads((jd / "job.json").read_text())
    data["stages"]["d1"]["run_id"] = bad
    (jd / "job.json").write_text(json.dumps(data))
    assert detail(svc)[0] == 404


def test_an_absolute_run_id_does_not_read_a_foreign_draft(svc, tmp_path):
    jd = make(svc)
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "draft.json").write_text((jd / "runs" / RUN / "draft.json").read_text())
    data = json.loads((jd / "job.json").read_text())
    data["stages"]["d1"]["run_id"] = str(foreign)
    (jd / "job.json").write_text(json.dumps(data))
    assert detail(svc)[0] == 404


def test_a_text_with_many_lines_is_not_diffed_so_the_server_cannot_be_stalled(svc):
    import time
    lines = [f"def test_{i % 600}():\n    assert {i % 600}\n" for i in range(6000)]
    make(svc, changed=[{"path": PATH, "content": "".join(reversed(lines))}], old="".join(lines))
    t0 = time.monotonic()
    d = detail(svc)[1]["tests"][0]
    assert d["diff"] is None and d["note"] == "the text is too long to diff here" and time.monotonic() - t0 < 5


def test_a_text_just_under_the_line_limit_is_diffed_and_fast(svc):
    import time
    lines = [f"l{i % 97}\n" for i in range(4900)]
    make(svc, changed=[{"path": PATH, "content": "".join(reversed(lines))}], old="".join(lines))
    t0 = time.monotonic()
    d = detail(svc)[1]["tests"][0]
    assert d["diff"] and time.monotonic() - t0 < 5


def test_identical_texts_give_an_empty_diff_the_page_can_name(svc):
    make(svc, changed=[{"path": PATH, "content": OLD}])
    assert detail(svc)[1]["tests"][0]["diff"] == ""


def test_a_long_diff_is_cut_at_a_line_end_and_says_so(svc):
    new = "".join("y" * 400 + f"{i:04d}\n" for i in range(450))                 # 180 KB of text: under the file limit, over the diff's 60 000 characters
    make(svc, changed=[{"path": PATH, "content": new}], old="")
    t = detail(svc)[1]["tests"][0]
    assert t["diff_cut"] is True and 0 < len(t["diff"]) <= 60_000
    added = [ln for ln in t["diff"].splitlines() if ln.startswith("+yy")]
    assert added and all(len(ln) == 405 for ln in added)                        # '+' + 400 y + 4 digits: no line is cut in the middle


def test_a_changed_tests_field_that_is_not_a_list_is_unreadable_not_empty(svc):
    make(svc, changed="junk")
    d = detail(svc)[1]
    assert d["tests_ok"] is False and d["tests_n"] == 0


def test_a_missing_or_empty_changed_tests_list_is_a_draft_that_only_adds_tests(svc):
    make(svc, changed=[])
    d = detail(svc)[1]
    assert d["tests_ok"] is True and d["tests_n"] == 0


def test_huge_lists_are_sliced_before_they_are_scrubbed(svc, monkeypatch):
    calls = []
    import router.chat_actions as ca2
    real = ca2.scrub
    monkeypatch.setattr(ca2, "scrub", lambda x: calls.append(1) or real(x))
    d = t4.draft()
    d["contract"]["scope"]["writable"] = [f"w{i}" for i in range(20000)]
    d["contract"]["validation"] = [{"id": "v", "must_pass": [f"t{i}" for i in range(20000)]}]
    d["changed_tests"] = []
    jd = t4.awaiting(svc, J, t4.TEXT, d=d)
    os.rename(jd / "runs" / "d1-run", jd / "runs" / RUN)
    data = json.loads((jd / "job.json").read_text())
    data["stages"]["d1"]["run_id"] = RUN
    (jd / "job.json").write_text(json.dumps(data))
    out = detail(svc)[1]
    assert len(out["writable"]) == 50 and len(out["must_pass"]) == 50 and len(calls) < 400


def test_a_draft_that_changes_more_files_than_the_limit_reads_only_the_first_ones(svc, monkeypatch):
    import router.chat_t4b as tb
    seen = []
    real = tb._read_below
    monkeypatch.setattr(tb, "_read_below", lambda base, parts, limit: seen.append(parts) or real(base, parts, limit))
    make(svc, changed=[{"path": f"tests/test_{n}.py", "content": NEW} for n in range(9)])
    detail(svc)
    assert len(seen) == 5
