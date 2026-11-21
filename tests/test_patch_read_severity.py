"""SPEC_PATCH_READER_SEVERITY: a `concerns` reading carries a severity; a pair of Argus readers whose every concern is a nit is the kind `nit`, which applies like `ok`."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from patch_read_util import read_argus_pair, read_pair  # noqa: E402
from test_apply_cmd import (edit_shop, env, g, head, home, package, untouched)  # noqa: E402,F401
from router import apply as ra  # noqa: E402
from router import job as rj  # noqa: E402
from router import patch_read as pr  # noqa: E402


def note_file(env):
    return [p for p in env.job().dir.iterdir() if p.name.startswith("patch_read_a")][0]


def kind_of(env, disk):
    return pr.load(env.job().dir, "a1", disk)[0]


def edit(env, fn):
    f = note_file(env)
    rec = json.loads(f.read_text())
    fn(rec)
    f.write_text(json.dumps(rec))


@pytest.mark.parametrize("first,sev1,second,sev2,kind", [
    ("concerns", "blocker", "concerns", "blocker", "concerns"),
    ("concerns", "nit", "ok", None, "nit"),
    ("ok", None, "concerns", "nit", "nit"),
    ("concerns", "nit", "concerns", "nit", "nit"),
    ("concerns", "nit", "concerns", "blocker", "concerns"),
    ("concerns", "blocker", "concerns", "nit", "concerns"),
    ("ok", None, "concerns", "blocker", "concerns"),
    ("ok", None, "ok", None, "ok"),
    ("concerns", None, "ok", None, "concerns"),                       # no severity said: a blocker
    ("ok", None, "concerns", None, "concerns"),
])
def test_the_kind_of_an_argus_pair_by_severity(env, tmp_path, first, sev1, second, sev2, kind):
    patch, sha = package(env, tmp_path, edit_shop())
    disk = read_argus_pair(env, first, second, sev1, sev2)
    assert kind_of(env, disk) == kind


def test_a_first_nit_alone_keeps_the_patch_closed_and_a_second_reading_can_still_be_added(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    disk = read_argus_pair(env, "concerns", None, "nit")
    assert kind_of(env, disk) == "concerns"


def test_only_the_two_argus_readers_can_make_a_nit_pair(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    disk = read_pair(env, "concerns", "ok")                                        # two Claude readings (kind claude)
    edit(env, lambda r: r.update(severity="nit"))
    assert kind_of(env, disk) == "concerns"
    edit(env, lambda r: r["reader"].update(kind="argus"))                          # kind argus but ids that are not the pair's
    edit(env, lambda r: r.update(template_sha256=pr.TEMPLATE_SHA256))
    edit(env, lambda r: r["second"].update(reader={"kind": "argus", "id": "someone-else"}, template_sha256=pr.TEMPLATE_SHA256))
    assert kind_of(env, disk) == "concerns"


def test_a_first_nit_with_a_damaged_stale_or_same_id_second_is_concerns_never_nit(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    disk = read_argus_pair(env, "concerns", "ok", "nit", None)
    assert kind_of(env, disk) == "nit"
    good = json.loads(note_file(env).read_text())
    for damage in (lambda r: r["second"].update(note=""), lambda r: r["second"].update(template_sha256="0" * 64),
                   lambda r: r["second"]["reader"].update(id=r["reader"]["id"]), lambda r: r["second"].update(severity="minor"),
                   lambda r: r["second"].pop("at")):
        note_file(env).write_text(json.dumps(good))
        edit(env, damage)
        assert kind_of(env, disk) == "concerns"


def test_severity_is_stored_for_concerns_only_and_the_second_record_keeps_the_first_ones(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    read_argus_pair(env, "concerns", "ok", "nit", None)
    rec = json.loads(note_file(env).read_text())
    assert rec["severity"] == "nit" and "severity" not in rec["second"]
    note_file(env).unlink()
    read_argus_pair(env, "ok", "concerns", "nit", "nit")
    rec = json.loads(note_file(env).read_text())
    assert "severity" not in rec and rec["second"]["severity"] == "nit"


def test_an_unknown_severity_and_a_severity_on_an_ok_make_the_note_unreadable_and_an_absent_one_a_blocker(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    disk = read_argus_pair(env, "concerns", "ok", "nit", None)
    good = note_file(env).read_text()
    edit(env, lambda r: r.update(severity="minor"))                                # an unknown value on the first reading
    assert kind_of(env, disk) == "error"
    note_file(env).write_text(good)
    edit(env, lambda r: r["second"].update(severity="nit"))                        # a severity on an ok second reading: after a first nit the patch stays closed
    assert kind_of(env, disk) == "concerns"
    note_file(env).unlink()
    disk = read_argus_pair(env, "ok", "ok")
    edit(env, lambda r: r.update(severity="nit"))                                  # a severity on an ok first reading
    assert kind_of(env, disk) == "error"
    note_file(env).unlink()
    read_argus_pair(env, "concerns", "ok", "nit", None)
    good = note_file(env).read_text()
    note_file(env).write_text(good)
    edit(env, lambda r: r.pop("severity"))
    assert kind_of(env, disk) == "concerns"


def test_a_nit_pair_is_never_written_over(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    disk = read_argus_pair(env, "concerns", "ok", "nit", None)
    with pytest.raises(rj.Refused, match="not written over"):
        pr.record("jtest", disk[:12], "ok", "again", "claude", "reader-x", deps=env.deps, jobs_dir=env.jobs)
    assert kind_of(env, disk) == "nit"


def test_findings_can_leave_the_nits_out_and_nits_lists_them(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    disk = read_argus_pair(env, "concerns", "concerns", "blocker", "nit")
    rec = pr.load(env.job().dir, "a1", disk)[1]
    assert len(pr.findings(rec)) == 2 and [w for w, _ in pr.findings(rec, blockers_only=True)] == [pr.findings(rec)[0][0]]
    assert [n for _, n in pr.nits(rec)] == ["second reading"]


# ---- apply -----------------------------------------------------------------------------------------------------------------------------

def test_apply_goes_through_on_a_nit_pair_records_the_nits_and_writes_the_plain_message(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    read_argus_pair(env, "ok", "concerns", None, "nit")
    job = ra.apply("jtest", sha[:12], deps=env.deps, jobs_dir=env.jobs)
    assert job.data["state"] == rj.APPLIED
    e = job.data["log"][-1]
    assert e["accepted_nits"] == [["argus:" + e["accepted_nits"][0][0].split(":", 1)[1], "second reading"]]
    assert [x for x in job.data["log"] if x.get("what") == "apply_started"][-1]["accepted_nits"] == e["accepted_nits"]
    msg = g(env.repo, "log", "-1", "--format=%B")
    assert msg.endswith(f"Argus-Job: jtest\nArgus-Patch-Sha256: {sha}") and "nit" not in msg.lower().split("argus-job")[1]
    assert "patch read: nit" in rj.status("jtest", jobs_dir=env.jobs) or job.data["state"] == rj.APPLIED


def test_apply_refuses_a_blocker_and_a_plain_ok_has_no_nits(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    read_argus_pair(env, "ok", "concerns", None, "blocker")
    before = head(env)
    with pytest.raises(rj.Refused, match="recorded concerns"):
        ra.apply("jtest", sha[:12], deps=env.deps, jobs_dir=env.jobs)
    untouched(env, before)


def test_accept_concerns_on_a_nit_pair_has_nothing_to_accept(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    read_argus_pair(env, "ok", "concerns", None, "nit")
    before = head(env)
    with pytest.raises(rj.Refused, match="nothing to accept"):
        ra.apply("jtest", sha[:12], deps=env.deps, jobs_dir=env.jobs, accept_concerns="a reason that is long enough")
    untouched(env, before)


def test_a_crash_after_the_commit_keeps_the_nits_in_the_healed_record(env, tmp_path, monkeypatch):
    patch, sha = package(env, tmp_path, edit_shop())
    read_argus_pair(env, "ok", "concerns", None, "nit")
    real = rj._record_applied

    def crash(*a, **k):
        raise KeyboardInterrupt("killed after the commit")
    monkeypatch.setattr(rj, "_record_applied", crash)
    with pytest.raises(KeyboardInterrupt):
        ra.apply("jtest", sha[:12], deps=env.deps, jobs_dir=env.jobs)
    monkeypatch.setattr(rj, "_record_applied", real)
    job = ra.apply("jtest", sha[:12], deps=env.deps, jobs_dir=env.jobs)
    assert job.data["log"][-1]["recovered"] is True and job.data["log"][-1]["accepted_nits"]


def test_the_status_names_a_nit_pair(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    read_argus_pair(env, "ok", "concerns", None, "nit")
    out = rj.status("jtest", jobs_dir=env.jobs)
    assert "patch read: nit" in out and "second reading" in out and "write the note first" not in out


def test_a_claude_reading_with_the_ids_of_the_pair_is_still_not_a_nit_pair(env, tmp_path):
    from router import patch_read_run as prr
    patch, sha = package(env, tmp_path, edit_shop())
    disk = read_argus_pair(env, "concerns", "ok", "nit", None)
    assert kind_of(env, disk) == "nit"
    edit(env, lambda r: r["reader"].update(kind="claude"))
    edit(env, lambda r: r.pop("template_sha256"))
    assert kind_of(env, disk) == "concerns"                                                         # the ids are the pair's, the kind is not argus


def test_a_nit_of_a_second_reader_that_is_not_the_pair_keeps_the_patch_closed_and_stays_out_of_a_retry(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    disk = pr_disk = read_pair(env, "ok", None)
    pr.record("jtest", disk[:12], "concerns", "a corner", "claude", "reader-b", deps=env.deps, jobs_dir=env.jobs, second=True, severity="nit")
    kind, rec = pr.load(env.job().dir, "a1", disk)
    assert kind == "concerns"                                                                      # a Claude nit is not enough to open the patch
    assert pr.findings(rec, blockers_only=True) == [] and [n for _, n in pr.nits(rec)] == ["a corner"]
