"""SPEC_KARTU_SETUJU section 5 (PR 3 of T3): `argus patch-read` writes the note of a patch reader (a Claude session, recorded as such: not a
human and not a proof), `patch_read_<sid>.json`, bound to (sid, patch sha256); `argus apply` refuses without an `ok` note for the very patch it
applies and records `reader` as a field of the log entries it already writes (no new kind of `what`)."""
import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_router as tr  # noqa: E402
from test_apply_cmd import (edit_shop, env, g, head, home, package, rewrite, untouched)  # noqa: E402,F401
from router import apply as ra  # noqa: E402
from router import job as rj  # noqa: E402
from router import patch_read as pr  # noqa: E402
from router import stage_data  # noqa: E402

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="posix")
sys.path.insert(0, str(tr.ROOT / "scripts"))


def read(env, sha, verdict="ok", note="only the shop line changes", twice=True, **kw):
    """The first reading, and (an `ok` that is meant to open the patch) the second one by another reader id (SPEC_KARTU_SETUJU 13.5)."""
    kw.setdefault("reader_id", "reader-a")
    out = pr.record("jtest", sha[:12], verdict, note, "claude", deps=env.deps, jobs_dir=env.jobs, **kw)
    if twice and verdict == "ok":
        pr.record("jtest", sha[:12], verdict, note, "claude", "reader-b", deps=env.deps, jobs_dir=env.jobs, second=True)
    return out


def file_of(env, sid="a1"):
    return env.job().dir / f"patch_read_{sid}.json"


def apply(env, sha, **kw):
    return ra.apply("jtest", sha[:12], deps=env.deps, jobs_dir=env.jobs, **kw)


# ---- record -------------------------------------------------------------------------------------------------------------------

def test_a_note_is_written_bound_to_the_stage_and_the_patch_and_nothing_else_changes(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    before = json.dumps(env.job().data, sort_keys=True)
    read(env, sha, reader_id="opus-session-1")
    rec = json.loads(file_of(env).read_text())
    assert rec["verdict"] == "ok" and rec["note"] == "only the shop line changes" and rec["sid"] == "a1" and rec["patch_sha256"] == sha
    assert rec["reader"] == {"kind": "claude", "id": "opus-session-1"} and rec["at"] and rec["key"] == pr.key("a1", sha)
    assert json.dumps(env.job().data, sort_keys=True) == before                      # job.json and its log are not touched: no new `what`
    assert not list(env.job().dir.glob("patch_read_*.tmp"))


def test_a_new_note_replaces_the_old_one_and_concerns_is_a_verdict_of_its_own(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    read(env, sha)
    assert pr.load(env.job().dir, "a1", sha)[0] == "ok"
    read(env, sha, verdict="concerns", note="it also writes a file")
    kind, rec = pr.load(env.job().dir, "a1", sha)
    assert kind == "concerns" and rec["note"] == "it also writes a file"


@pytest.mark.parametrize("kw,why", [
    ({"sha": "short"}, "sha"), ({"verdict": "fine"}, "verdict"), ({"note": ""}, "note"), ({"note": "   "}, "note"), ({"reader": "human"}, "reader"),
])
def test_a_bad_request_is_refused_and_writes_nothing(env, tmp_path, kw, why):
    patch, sha = package(env, tmp_path, edit_shop())
    args = {"sha": sha[:12], "verdict": "ok", "note": "n", "reader": "claude", **kw}
    with pytest.raises(rj.Refused, match=why):
        pr.record("jtest", args["sha"], args["verdict"], args["note"], args["reader"], deps=env.deps, jobs_dir=env.jobs)
    assert not file_of(env).exists()


def test_a_sha_that_is_not_the_patch_on_disk_is_refused(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    for bad in ("0" * 12, sha[:11], sha[:12][::-1]):
        with pytest.raises(rj.Refused):
            pr.record("jtest", bad, "ok", "n", "claude", deps=env.deps, jobs_dir=env.jobs)
    assert not file_of(env).exists()


def test_a_patch_the_review_did_not_record_is_not_read(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    d = Path(env.job().data["stages"]["a1"]["review"]["dir"])
    (d / "changes.patch").write_bytes(patch + b"\n")                               # changed after the review recorded it
    new = hashlib.sha256(patch + b"\n").hexdigest()
    with pytest.raises(rj.Refused, match="recorded"):
        pr.record("jtest", new[:12], "ok", "n", "claude", deps=env.deps, jobs_dir=env.jobs)
    assert not file_of(env).exists()


def test_only_a_job_with_a_package_to_apply_takes_a_note(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    job = env.job()
    with job.lock():
        job.data["state"] = rj.APPLIED
        job.save()
    with pytest.raises(rj.Refused, match="REVIEW_READY|APPLIED"):
        read(env, sha)


def test_the_note_text_is_cleaned_and_cut(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    read(env, sha, note="a\x00b‮c\n" + "x" * 2000, reader_id="id\x07" + "y" * 500)
    rec = json.loads(file_of(env).read_text())
    assert "\x00" not in rec["note"] and "‮" not in rec["note"] and "\n" not in rec["note"] and len(rec["note"]) <= pr.NOTE_MAX
    assert len(rec["reader"]["id"]) <= pr.ID_MAX and "\x07" not in rec["reader"]["id"]


def test_a_write_that_fails_leaves_the_earlier_note(env, tmp_path, monkeypatch):
    patch, sha = package(env, tmp_path, edit_shop())
    read(env, sha, note="first")
    monkeypatch.setattr(os, "replace", lambda *a, **k: (_ for _ in ()).throw(OSError("disk")))
    with pytest.raises(OSError):
        read(env, sha, note="second")
    monkeypatch.undo()
    assert pr.load(env.job().dir, "a1", sha)[1]["note"] == "first"


# ---- load ---------------------------------------------------------------------------------------------------------------------

def test_load_says_none_stale_or_error_never_ok_for_anything_else(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    d = env.job().dir
    assert pr.load(d, "a1", sha) == ("none", None)
    read(env, sha)
    assert pr.load(d, "a1", "0" * 64) == ("stale", None)                              # another patch
    assert pr.load(d, "a2", sha) == ("none", None)                                    # another stage has its own file
    rec = json.loads(file_of(env).read_text())
    bad = [
        (b"not json", "error"), (b"[]", "error"), (b"\xff\xfe", "error"), (json.dumps({**rec, "verdict": "fine"}).encode(), "error"),
        (json.dumps({**rec, "reader": "claude"}).encode(), "error"), (json.dumps({**rec, "reader": {"kind": "human"}}).encode(), "error"),
        (json.dumps({**rec, "note": 5}).encode(), "error"), (json.dumps({**rec, "note": ""}).encode(), "error"),
        (json.dumps({**rec, "key": "x"}).encode(), "error"), (json.dumps({k: v for k, v in rec.items() if k != "at"}).encode(), "error"),
        (json.dumps({**rec, "sid": "a2"}).encode(), "error"), (json.dumps({**rec, "patch_sha256": "0" * 64}).encode(), "error"),    # the key no longer fits
        (json.dumps({**rec, "note": "x" * (pr.NOTE_MAX + 1)}).encode(), "error"), (json.dumps({**rec, "note": "a\x1b[2Jb"}).encode(), "error"),
        (json.dumps({**rec, "at": "\x1b[31m"}).encode(), "error"), (json.dumps({**rec, "at": "yesterday"}).encode(), "error"),
        (json.dumps({**rec, "reader": {"kind": "claude", "id": "y" * (pr.ID_MAX + 1)}}).encode(), "error"),
        (json.dumps({**rec, "reader": {"kind": "claude", "id": 5}}).encode(), "error"),
        (json.dumps({**rec, "key": pr.key("a1", "0" * 64), "patch_sha256": "0" * 64}).encode(), "stale"),    # a good note of another patch
    ]
    for raw, kind in bad:
        file_of(env).write_bytes(raw)
        assert pr.load(d, "a1", sha)[0] == kind, raw
    os.remove(file_of(env))
    os.symlink(d / "job.json", file_of(env))                                         # a link is never followed
    assert pr.load(d, "a1", sha)[0] == "error"
    os.remove(file_of(env))
    os.mkfifo(file_of(env))                                                           # a FIFO neither blocks nor counts
    assert pr.load(d, "a1", sha)[0] == "error"
    os.remove(file_of(env))
    file_of(env).write_bytes(b"x" * (pr.FILE_MAX + 1))
    assert pr.load(d, "a1", sha)[0] == "error"


def test_a_planted_temporary_name_is_never_followed(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    victim = tmp_path / "victim.txt"
    victim.write_text("precious")
    os.symlink(victim, file_of(env).with_name(file_of(env).name + ".tmp"))
    read(env, sha)
    assert victim.read_text() == "precious" and pr.load(env.job().dir, "a1", sha)[0] == "ok"
    assert not list(env.job().dir.glob("patch_read_*.tmp"))


def test_a_note_of_the_first_stage_does_not_open_the_apply_of_a_later_one(env, tmp_path):
    import copy
    patch, sha = package(env, tmp_path, edit_shop())
    read(env, sha)
    job = env.job()
    with job.lock():
        job.data["stages"]["a2"] = copy.deepcopy(job.data["stages"]["a1"])
        job.save()
    assert rj.last_agent(env.job())[0] == "a2"
    before = head(env)
    with pytest.raises(rj.Refused, match="patch-read"):
        apply(env, sha)
    untouched(env, before)
    assert "patch read: none" in rj.status("jtest", jobs_dir=env.jobs)


def test_a_note_never_reaches_the_public_snapshot(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    read(env, sha, reader_id="session-7")
    out = tmp_path / "published"
    out.mkdir()
    stage_data.build(env.jobs, out)
    names = [p.name for p in out.rglob("*")]
    text = "".join(p.read_text(errors="replace") for p in out.rglob("*") if p.is_file())
    assert not any(n.startswith("patch_read") for n in names) and "session-7" not in text and "only the shop line changes" not in text


def test_the_stage_name_of_a_note_is_checked(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    for bad in ("../a1", "a1/../a1", "x", "", "a" * 40):
        assert pr.load(env.job().dir, bad, sha)[0] == "error"


# ---- apply --------------------------------------------------------------------------------------------------------------------

def test_apply_refuses_without_a_note_and_changes_nothing(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    before = head(env)
    with pytest.raises(rj.Refused, match="patch-read"):
        apply(env, sha)
    untouched(env, before)


def test_apply_refuses_when_the_reader_has_concerns_and_says_what_they_are(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    read(env, sha, verdict="concerns", note="it also writes a file")
    before = head(env)
    with pytest.raises(rj.Refused, match="concerns.*it also writes a file"):
        apply(env, sha)
    untouched(env, before)


def test_apply_refuses_a_note_for_another_patch(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    read(env, sha)
    patch2, sha2 = rewrite(env, patch + b"")                                         # same bytes: the note still holds
    assert sha2 == sha
    patch3, sha3 = package(env, tmp_path, edit_shop("# another\n"), name="s2")        # the package now says another patch
    before = head(env)
    with pytest.raises(rj.Refused, match="patch-read"):
        apply(env, sha3)
    untouched(env, before)


def test_apply_refuses_a_damaged_note(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    read(env, sha)
    file_of(env).write_text("{")
    before = head(env)
    with pytest.raises(rj.Refused, match="patch-read"):
        apply(env, sha)
    untouched(env, before)


def test_apply_with_an_ok_note_applies_and_records_the_reader_only_when_asked(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    read(env, sha)
    job = apply(env, sha, reader="claude")
    started = [e for e in job.data["log"] if e["what"] == "apply_started"][-1]
    done = job.data["log"][-1]
    assert job.data["state"] == rj.APPLIED and started["reader"] == "claude" and done["reader"] == "claude"
    assert not any("patch_read" in e["what"] or e["what"] == "patch-read" for e in job.data["log"])      # no new kind of `what`


def test_apply_without_the_reader_flag_logs_no_reader(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    read(env, sha)
    job = apply(env, sha)
    assert all("reader" not in e for e in job.data["log"])


def test_a_reader_that_is_not_claude_is_refused_by_apply(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    read(env, sha)
    with pytest.raises(rj.Refused, match="reader"):
        apply(env, sha, reader="human")


def test_the_reader_field_is_not_published_to_the_viewer():
    entry = {"at": "2026-11-17T10:00:00Z", "what": "apply_started", "read_sha": "abc", "reader": "claude"}
    out = stage_data._pick(entry, stage_data.LOG_FIELDS, "log")
    assert "reader" not in out and "read_sha" not in out and out["what"] == "apply_started"


# ---- the command --------------------------------------------------------------------------------------------------------------

def test_the_cli_writes_the_note_and_apply_takes_the_reader_flag(env, tmp_path, capsys):
    import argus
    patch, sha = package(env, tmp_path, edit_shop())
    base = ["--jobs-dir", str(env.jobs)]
    assert argus.main([*base, "patch-read", "jtest", "--sha", sha[:12], "--verdict", "ok", "--note", "only the shop line", "--reader", "claude",
                       "--reader-id", "s1"], deps=env.deps) == 0
    out = capsys.readouterr().out
    assert "ok" in out and sha[:12] in out and "not a human" in out
    assert argus.main([*base, "apply", "jtest", "--read-sha", sha[:12], "--reader", "claude"], deps=env.deps) != 0      # one reading is not an ok (rev 3)
    assert env.job().data["state"] == rj.REVIEW_READY
    assert argus.main([*base, "patch-read", "jtest", "--sha", sha[:12], "--verdict", "ok", "--note", "same line", "--reader", "claude", "--reader-id", "s2", "--second"],
                      deps=env.deps) == 0
    assert argus.main([*base, "apply", "jtest", "--read-sha", sha[:12], "--reader", "claude"], deps=env.deps) == 0
    assert env.job().data["state"] == rj.APPLIED and env.job().data["log"][-1]["reader"] == "claude"


@pytest.mark.parametrize("args", [
    ["--sha", "abc", "--verdict", "fine", "--note", "n", "--reader", "claude"], ["--sha", "abc", "--verdict", "ok", "--reader", "claude"],
    ["--sha", "abc", "--verdict", "ok", "--note", "n", "--reader", "human"], ["--verdict", "ok", "--note", "n", "--reader", "claude"],
    ["--sha", "abc", "--verdict", "ok", "--note", "n"],
])
def test_the_cli_requires_every_part_of_a_note(env, args):
    import argus
    with pytest.raises(SystemExit):
        argus.main(["--jobs-dir", str(env.jobs), "patch-read", "jtest", *args], deps=env.deps)
    assert not file_of(env).exists()


def test_status_tells_what_the_note_is_and_how_to_write_it(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    text = rj.status("jtest", jobs_dir=env.jobs)
    assert "patch read: none" in text and f"argus patch-read jtest --sha {sha[:12]}" in text
    read(env, sha)
    text = rj.status("jtest", jobs_dir=env.jobs)
    assert "patch read: ok by claude" in text and "not a human" in text
    read(env, sha, verdict="concerns", note="writes a file")
    assert "patch read: concerns" in rj.status("jtest", jobs_dir=env.jobs)


def test_a_crash_after_the_commit_is_healed_and_the_reader_is_still_recorded(env, tmp_path, monkeypatch):
    patch, sha = package(env, tmp_path, edit_shop())
    read(env, sha)
    real = rj._record_applied
    calls = []

    def die_once(*a, **k):
        calls.append(k.get("reader"))
        if len(calls) == 1:
            raise KeyboardInterrupt
        return real(*a, **k)
    monkeypatch.setattr(rj, "_record_applied", die_once)
    with pytest.raises(KeyboardInterrupt):
        apply(env, sha, reader="claude")
    done = apply(env, sha, reader="claude")
    assert done.data["state"] == rj.APPLIED and done.data["log"][-1]["reader"] == "claude" and calls == ["claude", "claude"]


def test_the_note_is_checked_before_the_repository_is_touched_even_for_a_second_call(env, tmp_path, monkeypatch):
    patch, sha = package(env, tmp_path, edit_shop())
    read(env, sha)
    real = rj._record_applied
    monkeypatch.setattr(rj, "_record_applied", lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt))
    with pytest.raises(KeyboardInterrupt):
        apply(env, sha)
    monkeypatch.setattr(rj, "_record_applied", real)
    os.remove(file_of(env))                                                          # the note is gone: even the healing call refuses
    with pytest.raises(rj.Refused, match="patch-read"):
        apply(env, sha)


# ---- the survivors of the first mutant run ---------------------------------------------------------------------------------------

def test_a_link_to_a_good_note_is_not_followed_and_a_padded_file_is_refused(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    read(env, sha)
    good = file_of(env).read_bytes()
    d = env.job().dir
    os.remove(file_of(env))
    elsewhere = tmp_path / "good.json"
    elsewhere.write_bytes(good)
    os.symlink(elsewhere, file_of(env))                                              # valid content, but through a link
    assert pr.load(d, "a1", sha)[0] == "error"
    os.remove(file_of(env))
    file_of(env).write_bytes(good + b" " * pr.FILE_MAX)                                # valid JSON, too big a file
    assert pr.load(d, "a1", sha)[0] == "error"


def test_the_limits_are_the_numbers_the_spec_shows(env, tmp_path):
    assert (pr.NOTE_MAX, pr.ID_MAX, pr.FILE_MAX) == (500, 80, 16 * 1024)
    patch, sha = package(env, tmp_path, edit_shop())
    read(env, sha, note="n" * 2000, reader_id="i" * 400)
    rec = json.loads(file_of(env).read_text())
    assert len(rec["note"]) == 500 and len(rec["reader"]["id"]) == 80


def test_the_key_depends_on_the_stage_and_the_patch():
    assert len({pr.key("a1", "0" * 64), pr.key("a2", "0" * 64), pr.key("a1", "1" * 64)}) == 3


def test_a_note_of_a_later_stage_is_its_own_file_and_opens_its_own_apply(env, tmp_path):
    import copy
    patch, sha = package(env, tmp_path, edit_shop())
    job = env.job()
    with job.lock():
        job.data["stages"]["a2"] = copy.deepcopy(job.data["stages"]["a1"])
        job.save()
    read(env, sha)
    assert file_of(env, "a2").exists() and not file_of(env, "a1").exists()
    assert json.loads(file_of(env, "a2").read_text())["sid"] == "a2"
    assert apply(env, sha).data["state"] == rj.APPLIED


def test_the_cli_keeps_the_reader_id(env, tmp_path, capsys):
    import argus
    patch, sha = package(env, tmp_path, edit_shop())
    argus.main(["--jobs-dir", str(env.jobs), "patch-read", "jtest", "--sha", sha[:12], "--verdict", "ok", "--note", "n", "--reader", "claude",
                "--reader-id", "session-9"], deps=env.deps)
    assert json.loads(file_of(env).read_text())["reader"] == {"kind": "claude", "id": "session-9"}


# ---- rev 3 (SPEC_KARTU_SETUJU 13.5): an ok is two readings by two different readers ------------------------------------------------

def test_one_ok_is_one_and_two_by_two_ids_are_ok_and_apply_refuses_the_first(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    read(env, sha, twice=False)
    kind, rec = pr.load(env.job().dir, "a1", sha)
    assert kind == "one" and rec["reader"]["id"] == "reader-a"
    with pytest.raises(rj.Refused, match="only one patch reading"):
        apply(env, sha)
    pr.record("jtest", sha[:12], "ok", "same", "claude", "reader-b", deps=env.deps, jobs_dir=env.jobs, second=True)
    kind, rec = pr.load(env.job().dir, "a1", sha)
    assert kind == "ok" and rec["second"]["reader"]["id"] == "reader-b"


def test_a_second_reading_needs_a_first_ok_and_another_id_and_a_concerns_is_not_written_over(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    with pytest.raises(rj.Refused, match="needs a first one"):
        pr.record("jtest", sha[:12], "ok", "n", "claude", "b", deps=env.deps, jobs_dir=env.jobs, second=True)
    read(env, sha, twice=False)
    for rid in ("reader-a", " READER-A ", None):
        with pytest.raises(rj.Refused, match="another reader id"):
            pr.record("jtest", sha[:12], "ok", "n", "claude", rid, deps=env.deps, jobs_dir=env.jobs, second=True)
    assert "second" not in json.loads(file_of(env).read_text())
    read(env, sha, verdict="concerns", note="it writes a file")                      # replaces the single ok: not a concerns yet
    with pytest.raises(rj.Refused, match="not written over"):
        read(env, sha, twice=False)
    pr.record("jtest", sha[:12], "ok", "n", "claude", "b", deps=env.deps, jobs_dir=env.jobs, second=True)     # a second reading is ADDED to a `concerns`: its findings are wanted too
    kind, rec = pr.load(env.job().dir, "a1", sha)
    assert kind == "concerns" and rec["verdict"] == "concerns" and rec["note"] == "it writes a file" and rec["second"]["verdict"] == "ok"
    with pytest.raises(rj.Refused, match="not written over"):                   # but not a third, and the first is never changed
        pr.record("jtest", sha[:12], "concerns", "n2", "claude", "c", deps=env.deps, jobs_dir=env.jobs, second=True)
    assert pr.load(env.job().dir, "a1", sha)[0] == "concerns"


def test_a_concerns_of_the_second_reading_closes_and_is_the_note_that_is_shown(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    read(env, sha, twice=False)
    pr.record("jtest", sha[:12], "concerns", "the second sees a write", "claude", "reader-b", deps=env.deps, jobs_dir=env.jobs, second=True)
    kind, rec = pr.load(env.job().dir, "a1", sha)
    assert kind == "concerns" and rec["note"] == "the second sees a write" and rec["reader"]["id"] == "reader-b"
    with pytest.raises(rj.Refused, match="recorded concerns"):
        apply(env, sha)


def test_a_damaged_or_same_id_second_reading_in_the_file_is_never_ok(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    read(env, sha)
    good = json.loads(file_of(env).read_text())
    for second in ({**good["second"], "reader": {"kind": "claude", "id": "Reader-A"}}, {**good["second"], "verdict": "fine"}, {**good["second"], "note": ""},
                   {**good["second"], "at": "yesterday"}, {**good["second"], "reader": {"kind": "human"}}, "x", {**good["second"], "note": "a\x1b[2J"}):
        file_of(env).write_text(json.dumps({**good, "second": second}))
        assert pr.load(env.job().dir, "a1", sha)[0] in ("one", "error"), second
    file_of(env).write_text(json.dumps({**good, "reader": {"kind": "claude"}}))              # the first reader has no id: not two readers
    assert pr.load(env.job().dir, "a1", sha)[0] == "one"


def test_a_second_reading_without_an_id_is_not_a_second_reader_and_a_model_reading_of_another_template_is_stale(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    read(env, sha)
    good = json.loads(file_of(env).read_text())
    file_of(env).write_text(json.dumps({**good, "second": {**good["second"], "reader": {"kind": "claude"}}}))
    assert pr.load(env.job().dir, "a1", sha)[0] == "one"
    # a model reading carries the hash of the template it was given
    file_of(env).write_text(json.dumps(good))
    assert pr.load(env.job().dir, "a1", sha)[0] == "ok"                                      # Claude readings have no template to be stale against
    for which in ("first", "second"):
        m = json.loads(json.dumps(good))
        part = m if which == "first" else m["second"]
        part["reader"] = {"kind": "argus", "id": "argus:x" if which == "first" else "argus:y"}
        part["template_sha256"] = pr.TEMPLATE_SHA256
        file_of(env).write_text(json.dumps(m))
        assert pr.load(env.job().dir, "a1", sha)[0] == "ok", which                         # the pair of models under the current template
        part["template_sha256"] = "0" * 64
        file_of(env).write_text(json.dumps(m))
        assert pr.load(env.job().dir, "a1", sha)[0] == "stale", which
        del part["template_sha256"]
        file_of(env).write_text(json.dumps(m))
        assert pr.load(env.job().dir, "a1", sha)[0] == "stale", which


def test_the_model_reader_is_a_reader_kind_and_the_template_is_the_tested_one():
    assert "argus" in pr.READERS and "claude" in pr.READERS
    assert pr.TEMPLATE_SHA256 == "05ce799f3234a2ffaf8f68eb7cfcbd8727d96fc55cda7ee3d270f522e9af0c2a"       # what the planted-patch trial tested; a change is a new trial


def test_when_both_readings_say_concerns_the_first_is_what_is_shown(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    read(env, sha)
    good = json.loads(file_of(env).read_text())
    file_of(env).write_text(json.dumps({**good, "verdict": "concerns", "note": "first sees a write", "second": {**good["second"], "verdict": "concerns", "note": "second sees a default"}}))
    kind, rec = pr.load(env.job().dir, "a1", sha)
    assert kind == "concerns" and rec["note"] == "first sees a write" and rec["reader"]["id"] == "reader-a"


def test_findings_lists_every_concerns_reading_in_order_and_nothing_for_an_ok(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    read(env, sha, verdict="concerns", note="first sees a write")
    pr.record("jtest", sha[:12], "concerns", "second sees a default", "claude", "reader-b", deps=env.deps, jobs_dir=env.jobs, second=True)
    kind, rec = pr.load(env.job().dir, "a1", sha)
    assert pr.findings(rec) == [("reader-a", "first sees a write"), ("reader-b", "second sees a default")]
    assert pr.findings({"verdict": "ok", "note": "fine", "reader": {"kind": "claude"}}) == []
    with pytest.raises(rj.Refused, match="first sees a write.*second sees a default"):
        apply(env, sha)
