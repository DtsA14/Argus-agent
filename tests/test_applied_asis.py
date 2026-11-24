"""SPEC_ARGUS_APPLY PR 1: `argus applied` compares the commit's changes with the patch the way the package makes the patch (binary, full index, no
renames, no textconv), with no GIT_* variable and no local diff configuration getting in; the review stage records the patch's sha256 in job.json;
and the recording is one function that does not take the job lock (so `argus apply` can hold it across its git work)."""
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_router as tr  # noqa: E402
from router import job as rj  # noqa: E402

td = tr.td
pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="posix")


@pytest.fixture
def env(tmp_path):
    e = tr.Env(tmp_path)
    e.code()
    e.approve()
    return e


def package_patch(env):
    return env.job().runs / "jtest-a1" / "review" / "changes.patch"


def make_patch(env, tmp_path, change):
    """A patch built as codetask/review.py builds it, for `change(scratch repo)` made on a copy of the target repo; written over the package's."""
    scratch = tmp_path / "scratch"
    shutil.copytree(env.repo, scratch)
    change(scratch)
    td.git(scratch, "add", "-A", "-f")
    out = subprocess.run(["git", "-C", str(scratch), "diff", "--cached", "--binary", "--full-index", "--no-renames", "--no-color", "--no-ext-diff"],
                         capture_output=True, check=True).stdout
    package_patch(env).write_bytes(out)
    return out


def commit_patch(env, patch):
    p = env.repo.parent / "applying.patch"
    p.write_bytes(patch)
    td.git(env.repo, "apply", str(p))
    td.git(env.repo, "add", "-A")
    td.git(env.repo, "commit", "-qm", "apply")


def as_is(env):
    return rj.applied("jtest", "HEAD", deps=env.deps, jobs_dir=env.jobs).data["log"][-1]["as_is"]


def test_a_binary_change_goes_in_as_it_was(env, tmp_path):
    commit_patch(env, make_patch(env, tmp_path, lambda r: (r / "logo.bin").write_bytes(b"\x00\x01\x02binary\xff" * 20)))
    assert as_is(env) is True


def test_a_file_move_goes_in_as_it_was(env, tmp_path):
    commit_patch(env, make_patch(env, tmp_path, lambda r: (r / "tests" / "test_old.py").rename(r / "tests" / "test_older.py")))
    assert as_is(env) is True


@pytest.mark.parametrize("key, value", [("diff.noprefix", "true"), ("diff.renames", "copies"), ("diff.context", "1"),
                                        ("diff.mnemonicPrefix", "true"), ("diff.algorithm", "patience")])
def test_local_diff_configuration_does_not_change_the_comparison(env, tmp_path, key, value):
    patch = make_patch(env, tmp_path, lambda r: (r / "src" / "shop.py").write_text(td.FIXED + "\n\n\n# more\n"))
    td.git(env.repo, "config", key, value)                   # after the patch is built: the package's patch is made without it
    commit_patch(env, patch)
    assert as_is(env) is True


def test_a_textconv_driver_of_the_repository_does_not_run(env, tmp_path):
    mark = tmp_path / "textconv-ran"
    script = tmp_path / "conv.sh"
    script.write_text(f"#!/bin/sh\ntouch {mark}\ncat \"$1\"\n")
    script.chmod(0o755)
    patch = make_patch(env, tmp_path, lambda r: (r / "src" / "shop.py").write_text(td.FIXED + "\n# x\n"))
    td.git(env.repo, "config", "diff.pyx.textconv", str(script))
    (env.repo / ".git" / "info").mkdir(exist_ok=True)
    (env.repo / ".git" / "info" / "attributes").write_text("*.py diff=pyx\n")
    commit_patch(env, patch)
    assert as_is(env) is True and not mark.exists()


def test_inherited_git_variables_do_not_redirect_the_commands(env, tmp_path, monkeypatch):
    other = tmp_path / "other"
    td.git(tmp_path, "init", "-q", str(other))
    commit_patch(env, make_patch(env, tmp_path, lambda r: (r / "src" / "shop.py").write_text(td.FIXED + "\n# y\n")))
    monkeypatch.setenv("GIT_DIR", str(other / ".git"))
    assert as_is(env) is True


def test_an_inherited_object_directory_does_not_redirect_the_commands(env, tmp_path, monkeypatch):
    commit_patch(env, make_patch(env, tmp_path, lambda r: (r / "src" / "shop.py").write_text(td.FIXED + "\n# v\n")))
    monkeypatch.setenv("GIT_OBJECT_DIRECTORY", str(tmp_path / "no-objects-here"))
    assert as_is(env) is True


def test_a_patch_changed_by_hand_is_still_told_apart(env, tmp_path):
    commit_patch(env, make_patch(env, tmp_path, lambda r: (r / "logo.bin").write_bytes(b"\x00abc")))
    (env.repo / "logo.bin").write_bytes(b"\x00abd")
    td.git(env.repo, "commit", "-qam", "touch")
    assert as_is(env) is False


def test_the_review_stage_records_the_patchs_sha256_in_the_job(env):
    rec = env.job().data["stages"]["a1"]["review"]
    assert rec["patch_sha256"] == hashlib.sha256(package_patch(env).read_bytes()).hexdigest()


def test_the_recording_is_one_function_that_does_not_take_the_lock(env, tmp_path):
    commit_patch(env, make_patch(env, tmp_path, lambda r: (r / "src" / "shop.py").write_text(td.FIXED + "\n# z\n")))
    job = rj.open_job("jtest", env.jobs)
    with job.lock():                                         # apply holds this across its git work and then records
        rj._record_applied(job, "HEAD", deps=env.deps, note="n", method="apply", head_before="abc")
    e = rj.open_job("jtest", env.jobs).data["log"][-1]
    assert e["new"] == rj.APPLIED and e["as_is"] is True and e["method"] == "apply" and e["head_before"] == "abc" and e["note"] == "n"


def test_applied_still_takes_the_lock_and_still_refuses_a_job_that_is_not_ready(env, tmp_path):
    commit_patch(env, make_patch(env, tmp_path, lambda r: (r / "src" / "shop.py").write_text(td.FIXED + "\n# w\n")))
    held = rj.open_job("jtest", env.jobs)
    with held.lock():
        with pytest.raises(rj.Refused):
            rj.applied("jtest", "HEAD", deps=env.deps, jobs_dir=env.jobs)
    rj.applied("jtest", "HEAD", deps=env.deps, jobs_dir=env.jobs)
    with pytest.raises(rj.Refused, match="only a valid review package is applied"):
        rj.applied("jtest", "HEAD", deps=env.deps, jobs_dir=env.jobs)


# ---- the comparison itself, on a file with room for hunks, odd paths and local settings --------------------------------------------------

def lines(n, edit=()):
    return "".join(f"line {i}{' edited' if i in edit else ''}\n" for i in range(1, n + 1))


def asis_of(tmp_path, *, config=(), env=None, edit=(10, 20), path="data.txt"):      # 9 lines between the hunks: past the context, within interHunkContext=10
    """as_is as `applied` computes it, on a repository made here: the package's patch (built as codetask/review.py builds it) against the commit."""
    repo = tmp_path / "r"
    td.git(tmp_path, "init", "-q", str(repo))
    td.git(repo, "config", "user.email", "t@example.org")
    td.git(repo, "config", "user.name", "t")
    (repo / path).write_text(lines(40))
    td.git(repo, "add", "-A")
    td.git(repo, "commit", "-qm", "base")
    scratch = tmp_path / "s"
    shutil.copytree(repo, scratch)
    (scratch / path).write_text(lines(40, edit))
    td.git(scratch, "add", "-A", "-f")
    patch = subprocess.run(["git", "-C", str(scratch), "diff", "--cached", "--binary", "--full-index", "--no-renames", "--no-color", "--no-ext-diff"],
                           capture_output=True, check=True).stdout
    (repo / path).write_text(lines(40, edit))
    td.git(repo, "add", "-A")
    td.git(repo, "commit", "-qm", "apply")
    for k, v in config:
        td.git(repo, "config", k, v)
    for k, v in (env or {}).items():
        os.environ[k] = v
    try:
        sha = rj.intake.git(repo, "rev-parse", "HEAD", clean=True).decode().strip()
        return rj.patch_id(repo, patch) == rj.patch_id(repo, rj.intake.git(repo, *rj.SHOW_AS_PACKAGED, sha, clean=True))
    finally:
        for k in env or {}:
            os.environ.pop(k, None)


@pytest.mark.parametrize("config", [(), (("diff.context", "1"),), (("diff.interHunkContext", "10"),), (("diff.algorithm", "patience"),),
                                    (("diff.indentHeuristic", "false"),), (("color.ui", "always"),), (("diff.noprefix", "true"),)])
def test_local_settings_do_not_change_the_comparison_on_a_file_with_two_nearby_hunks(tmp_path, config):
    assert asis_of(tmp_path, config=config) is True


def test_a_non_ascii_path_is_compared_as_the_package_writes_it(tmp_path):
    assert asis_of(tmp_path, config=(("core.quotePath", "false"),), path="données é.txt") is True


def test_an_external_diff_program_does_not_run(tmp_path):
    mark = tmp_path / "ext-ran"
    script = tmp_path / "ext.sh"
    script.write_text(f"#!/bin/sh\ntouch {mark}\n")
    script.chmod(0o755)
    assert asis_of(tmp_path, config=(("diff.external", str(script)),)) is True and not mark.exists()


def test_a_missing_patch_is_a_refusal_not_a_traceback(env, tmp_path):
    commit_patch(env, make_patch(env, tmp_path, lambda r: (r / "src" / "shop.py").write_text(td.FIXED + "\n# m\n")))
    package_patch(env).unlink()
    with pytest.raises(rj.Refused):
        rj.applied("jtest", "HEAD", deps=env.deps, jobs_dir=env.jobs)
    assert env.job().data["state"] == rj.REVIEW_READY


def test_a_git_timeout_is_a_refusal(env, tmp_path, monkeypatch):
    commit_patch(env, make_patch(env, tmp_path, lambda r: (r / "src" / "shop.py").write_text(td.FIXED + "\n# t\n")))

    def slow(*a, **k):
        raise subprocess.TimeoutExpired("git", 1)
    monkeypatch.setattr(rj.intake, "git", slow)
    with pytest.raises(rj.Refused):
        rj.applied("jtest", "HEAD", deps=env.deps, jobs_dir=env.jobs)


def test_the_recorded_sha_is_of_the_bytes_that_were_compared(env, tmp_path):
    commit_patch(env, make_patch(env, tmp_path, lambda r: (r / "src" / "shop.py").write_text(td.FIXED + "\n# r\n")))
    reads = []
    real = Path.read_bytes

    def counting(self):
        if self.name == "changes.patch":
            reads.append(1)
        return real(self)
    Path.read_bytes = counting
    try:
        rj.applied("jtest", "HEAD", deps=env.deps, jobs_dir=env.jobs)
    finally:
        Path.read_bytes = real
    assert len(reads) == 1


@pytest.mark.parametrize("field", ["at", "what", "old", "new", "patch_sha256", "as_is", "by", "actor"])
def test_the_recorder_refuses_fields_that_are_the_log_entrys_own(env, tmp_path, field):
    commit_patch(env, make_patch(env, tmp_path, lambda r: (r / "src" / "shop.py").write_text(td.FIXED + "\n# q\n")))
    job = rj.open_job("jtest", env.jobs)
    with job.lock(), pytest.raises(ValueError, match="log entry itself"):
        rj._record_applied(job, "HEAD", deps=env.deps, **{field: "x"})


@pytest.mark.parametrize("claudecode,expect", [("1", "claude"), (None, "terminal")])
def test_the_applied_record_says_who_ran_the_command(env, tmp_path, monkeypatch, claudecode, expect):
    (monkeypatch.setenv("CLAUDECODE", claudecode) if claudecode else monkeypatch.delenv("CLAUDECODE", raising=False))
    commit_patch(env, make_patch(env, tmp_path, lambda r: (r / "src" / "shop.py").write_text(td.FIXED + "\n# q\n")))
    job = rj.applied("jtest", "HEAD", deps=env.deps, jobs_dir=env.jobs)
    assert job.data["log"][-1]["actor"] == expect
