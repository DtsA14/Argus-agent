"""SPEC_ARGUS_APPLY PR 2: `argus apply <job> --read-sha <sha>`: the review package's patch goes into the target repository and one commit is made, with the
repository's own code never run, every refusal leaving the repository and the job as they were, and a crash after the commit healed by a second call."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_router as tr  # noqa: E402
from patch_read_util import read_ok, read_pair  # noqa: E402
from router import apply as ra  # noqa: E402
from router import job as rj  # noqa: E402

td = tr.td
pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="posix")


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    """A HOME of its own: the identity the command reads is the test's, never the developer's."""
    h = tmp_path / "home"
    h.mkdir()
    (h / ".gitconfig").write_text("[user]\n\tname = Global Person\n\temail = global@example.org\n")
    monkeypatch.setenv("HOME", str(h))
    for k in [k for k in os.environ if k.startswith("GIT_")]:
        monkeypatch.delenv(k)
    return h


@pytest.fixture
def env(tmp_path):
    e = tr.Env(tmp_path)
    e.code()
    e.approve()
    return e


def g(repo, *args, check=True):
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull})
    assert r.returncode == 0 or not check, r.stderr
    return r.stdout.strip()


def head(env):
    return g(env.repo, "rev-parse", "HEAD")


def package(env, tmp_path, change, name="s"):
    """Make the package say `change` (made on a copy of the repository, as the package is made); returns (patch bytes, its sha256 hex)."""
    scratch = tmp_path / name
    shutil.copytree(env.repo, scratch)
    change(scratch)
    td.git(scratch, "add", "-A", "-f")
    patch = subprocess.run(["git", "-C", str(scratch), "diff", "--cached", "--binary", "--full-index", "--no-renames", "--no-color", "--no-ext-diff"],
                           capture_output=True, check=True).stdout
    files = [{"path": p, "change": "M"} for p in g(scratch, "diff", "--cached", "--name-only", "--no-renames", "-z").split("\0") if p]
    return rewrite(env, patch, files)


def rewrite(env, patch, files=None):
    job = env.job()
    d = Path(job.data["stages"]["a1"]["review"]["dir"])
    (d / "changes.patch").write_bytes(patch)
    sha = hashlib.sha256(patch).hexdigest()
    prov = json.loads((d / "provenance.json").read_text())
    prov["patch"]["sha256"] = sha
    if files is not None:
        prov["patch"]["files"] = files
    (d / "provenance.json").write_text(json.dumps(prov))
    job.data["stages"]["a1"]["review"]["patch_sha256"] = sha
    job.save()
    return patch, sha


def edit_shop(extra="# apply\n"):
    return lambda r: (r / "src" / "shop.py").write_text(td.FIXED + "\n" + extra)


def run_apply(env, sha, **kw):
    read_ok(env, sha)
    return ra.apply("jtest", sha[:12], deps=env.deps, jobs_dir=env.jobs, **kw)


def untouched(env, before):
    assert head(env) == before and g(env.repo, "status", "--porcelain", "--untracked-files=all") == ""
    assert env.job().data["state"] == rj.REVIEW_READY


# ---- the good paths -----------------------------------------------------------------------------------------------------------------

def test_the_patch_goes_in_as_one_commit_on_the_current_branch_and_the_job_is_applied(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    before, branch = head(env), g(env.repo, "symbolic-ref", "--short", "HEAD")
    job = run_apply(env, sha, note="n")
    new = head(env)
    assert new != before and g(env.repo, "rev-parse", "HEAD^") == before and g(env.repo, "symbolic-ref", "--short", "HEAD") == branch
    msg = g(env.repo, "log", "-1", "--format=%B")
    assert "Argus-Job: jtest" in msg and f"Argus-Patch-Sha256: {sha}" in msg and msg.splitlines()[0]
    assert g(env.repo, "status", "--porcelain", "--untracked-files=all") == ""
    e = job.data["log"][-1]
    assert job.data["state"] == rj.APPLIED and e["commit"] == new and e["as_is"] is True and e["method"] == "apply"
    assert e["head_before"] == before and e["branch"] == branch and e["read_sha"] == sha[:12] and e["note"] == "n"
    assert "Global Person" in g(env.repo, "log", "-1", "--format=%an")                # no local identity: the global one, read once


@pytest.mark.parametrize("change", [
    lambda r: (r / "logo.bin").write_bytes(b"\x00\x01binary\xff" * 30),
    lambda r: (r / "tests" / "test_old.py").rename(r / "tests" / "test_older.py"),
    lambda r: (r / "src" / "shop.py").unlink(),
    lambda r: (r / "tests" / "test_old.py").chmod(0o755),
    lambda r: (r / "notes.txt").write_bytes(b"no final newline"),
    lambda r: (r / "naïve é.txt").write_text("unicode path\n"),
    lambda r: (r / ".gitignore").write_text("*.cache\n"),
])
def test_binary_move_delete_mode_no_newline_unicode_and_gitignore_changes_go_in_as_they_were(env, tmp_path, change):
    patch, sha = package(env, tmp_path, change)
    job = run_apply(env, sha)
    assert job.data["state"] == rj.APPLIED and job.data["log"][-1]["as_is"] is True
    assert subprocess.run(["git", "-C", str(env.repo), "diff", "--cached", "--quiet"]).returncode == 0
    assert g(env.repo, "status", "--porcelain", "--untracked-files=all") == ""


def test_a_repository_with_only_a_global_identity_and_one_with_a_local_one_both_work(env, tmp_path):
    g(env.repo, "config", "user.name", "Local Person")
    g(env.repo, "config", "user.email", "local@example.org")
    patch, sha = package(env, tmp_path, edit_shop())
    run_apply(env, sha)
    assert g(env.repo, "log", "-1", "--format=%an <%ae>") == "Local Person <local@example.org>"


def test_the_status_prints_the_command_with_the_sha_to_read_and_the_manual_steps_stay(env):
    text = rj.status("jtest", jobs_dir=env.jobs)
    sha = hashlib.sha256((Path(env.job().data["stages"]["a1"]["review"]["dir"]) / "changes.patch").read_bytes()).hexdigest()
    assert f"argus apply jtest --read-sha {sha[:12]}" in text and "git -C" in text


def test_the_cli_applies_and_prints_the_status(env, tmp_path, capsys):
    sys.path.insert(0, str(tr.ROOT / "scripts"))
    import argus
    patch, sha = package(env, tmp_path, edit_shop())
    read_ok(env, sha)
    assert argus.main(["--jobs-dir", str(env.jobs), "apply", "jtest", "--read-sha", sha[:12]], deps=env.deps) == 0
    assert "applied: commit" in capsys.readouterr().out and env.job().data["state"] == rj.APPLIED
    with pytest.raises(SystemExit):
        argus.main(["--jobs-dir", str(env.jobs), "apply", "jtest"], deps=env.deps)                  # --read-sha is required


# ---- refusals: nothing changes -----------------------------------------------------------------------------------------------------

def refused(env, tmp_path, sha, match=None, **kw):
    before = head(env)
    with pytest.raises(rj.Refused, match=match):
        run_apply(env, sha, **kw)
    untouched(env, before)


def test_a_wrong_short_or_empty_read_sha_is_refused(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    for bad in ("0" * 12, sha[:11], ""):
        before = head(env)
        with pytest.raises(rj.Refused):
            ra.apply("jtest", bad, deps=env.deps, jobs_dir=env.jobs)
        untouched(env, before)


def test_a_patch_changed_after_it_was_read_is_refused(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    d = Path(env.job().data["stages"]["a1"]["review"]["dir"])
    (d / "changes.patch").write_bytes(patch + b"\n")
    refused(env, tmp_path, hashlib.sha256(patch + b"\n").hexdigest(), "recorded|changed|sha")


def test_a_provenance_that_does_not_name_the_patch_is_refused(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    d = Path(env.job().data["stages"]["a1"]["review"]["dir"])
    prov = json.loads((d / "provenance.json").read_text())
    prov["patch"]["sha256"] = "0" * 64
    (d / "provenance.json").write_text(json.dumps(prov))
    refused(env, tmp_path, sha)


def test_a_job_from_before_the_recorded_sha_is_refused_with_the_manual_way(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    job = env.job()
    job.data["stages"]["a1"]["review"].pop("patch_sha256")
    job.save()
    refused(env, tmp_path, sha, "predates")


def test_the_file_list_must_be_the_one_the_package_names(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    rewrite(env, patch, [{"path": "src/other.py", "change": "M"}])
    refused(env, tmp_path, sha, "files|list")


def test_a_protected_file_in_the_patch_is_refused_again(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    job = env.job()
    job.data["protected_repo"] = {"sha256": "x", "globs": ["src/*.py"]}
    job.save()
    refused(env, tmp_path, sha, "protected")


@pytest.mark.parametrize("what", ["tracked", "untracked"])
def test_a_dirty_tree_is_refused(env, tmp_path, what):
    patch, sha = package(env, tmp_path, edit_shop())
    (env.repo / ("conftest.py" if what == "tracked" else "new.txt")).write_text("x\n")
    before = head(env)
    with pytest.raises(rj.Refused, match="clean|dirty"):
        run_apply(env, sha)
    assert head(env) == before and env.job().data["state"] == rj.REVIEW_READY


def test_a_detached_head_and_a_head_that_is_not_the_base_commit_are_refused(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    (env.repo / "later.txt").write_text("later\n")
    g(env.repo, "add", "-A")
    td.git(env.repo, "commit", "-qm", "later")
    refused(env, tmp_path, sha, "base|HEAD")
    g(env.repo, "checkout", "-q", "--detach")
    refused(env, tmp_path, sha, "branch|detached")


def test_a_branch_checked_out_in_another_worktree_is_refused(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    branch = g(env.repo, "symbolic-ref", "--short", "HEAD")
    g(env.repo, "checkout", "-q", "-b", "other")
    g(env.repo, "worktree", "add", "-q", str(tmp_path / "wt"), branch)
    g(env.repo, "checkout", "-q", branch, check=False)
    # the main worktree is on "other" now and wt holds the branch the base is on: apply from a repository whose current branch is borrowed
    shutil.rmtree(env.repo / "nothing", ignore_errors=True)
    g(env.repo, "worktree", "remove", "--force", str(tmp_path / "wt"))
    g(env.repo, "checkout", "-q", branch)
    g(env.repo, "worktree", "add", "-q", "--detach", str(tmp_path / "wt2"))
    g(tmp_path / "wt2", "checkout", "-q", "--ignore-other-worktrees", branch)
    refused(env, tmp_path, sha, "worktree")


@pytest.mark.parametrize("path, content", [
    ("sub/.gitattributes", "*.py text\n"), (".gitattributes", "*.py text\n"), (".gitmodules", "[submodule \"x\"]\n"),
])
def test_a_patch_touching_git_metadata_files_is_refused_at_any_depth(env, tmp_path, path, content):
    def change(r):
        (r / path).parent.mkdir(parents=True, exist_ok=True)
        (r / path).write_text(content)
    patch, sha = package(env, tmp_path, change)
    refused(env, tmp_path, sha, "git metadata|gitattributes|gitmodules|not allowed")


def test_a_patch_that_makes_a_symlink_is_refused(env, tmp_path):
    patch, sha = package(env, tmp_path, lambda r: os.symlink("/etc/passwd", r / "link"))
    refused(env, tmp_path, sha, "symlink|120000|mode")


def test_an_empty_patch_and_a_patch_that_does_not_apply_are_refused(env, tmp_path):
    patch, sha = rewrite(env, b"", [])
    refused(env, tmp_path, sha, "the patch is empty")
    bad = (b"diff --git a/src/shop.py b/src/shop.py\n--- a/src/shop.py\n+++ b/src/shop.py\n@@ -1,2 +1,2 @@\n-nothing like it\n+x\n")
    patch, sha = rewrite(env, bad, [{"path": "src/shop.py", "change": "M"}])
    refused(env, tmp_path, sha)


@pytest.mark.parametrize("key, value", [("filter.x.clean", "cat"), ("core.fsmonitor", "true"), ("include.path", "/dev/null"),
                                        ("diff.x.textconv", "cat"), ("commit.gpgsign", "true"), ("core.hooksPath", "/tmp/h"),
                                        ("alias.st", "status"), ("core.sshCommand", "ssh"), ("core.worktree", "/tmp"),
                                        ("core.attributesFile", "/tmp/a"), ("gpg.program", "/bin/true"), ("diff.external", "/bin/true")])
def test_a_local_configuration_outside_the_allowlist_is_refused_by_name(env, tmp_path, key, value):
    patch, sha = package(env, tmp_path, edit_shop())
    g(env.repo, "config", key, value)
    before = head(env)
    with pytest.raises(rj.Refused, match=key.split(".")[0] + "|top level"):          # core.worktree moves git's top level: refused for that, still refused
        run_apply(env, sha)
    g(env.repo, "config", "--unset", key)                                        # the check below reads the repository with git: without the key
    untouched(env, before)


def test_without_any_identity_the_command_refuses_and_makes_none_up(env, tmp_path, home):
    patch, sha = package(env, tmp_path, edit_shop())
    (home / ".gitconfig").unlink()
    refused(env, tmp_path, sha, "no git identity")


def test_a_repository_that_is_gone_or_is_the_argus_checkout_is_refused(env, tmp_path, monkeypatch):
    patch, sha = package(env, tmp_path, edit_shop())
    monkeypatch.setattr(ra, "ROOT", env.repo.resolve())
    before = head(env)
    with pytest.raises(rj.Refused, match="Argus"):
        run_apply(env, sha)
    monkeypatch.undo()
    shutil.move(env.repo, tmp_path / "moved")
    with pytest.raises(rj.Refused):
        run_apply(env, sha)
    shutil.move(tmp_path / "moved", env.repo)
    assert head(env) == before


def test_a_job_that_is_not_review_ready_and_a_second_apply_are_refused(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    run_apply(env, sha)
    with pytest.raises(rj.Refused, match="only a valid review package"):
        run_apply(env, sha)


# ---- the repository's own code does not run, and the caller's environment does not steer ------------------------------------------------

def test_hooks_of_the_repository_do_not_run(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())          # before the hooks exist: the scratch copy of the repository would run them
    marks = []
    for name in ("pre-commit", "commit-msg", "post-commit", "post-index-change", "prepare-commit-msg", "post-applypatch", "pre-applypatch"):
        mark = tmp_path / f"ran-{name}"
        hook = env.repo / ".git" / "hooks" / name
        hook.write_text(f"#!/bin/sh\ntouch {mark}\n")
        hook.chmod(0o755)
        marks.append(mark)
    run_apply(env, sha)
    assert not [m for m in marks if m.exists()]


def test_variables_of_the_caller_do_not_steer_the_git_commands(env, tmp_path, monkeypatch):
    patch, sha = package(env, tmp_path, edit_shop())
    other = tmp_path / "other"
    td.git(tmp_path, "init", "-q", str(other))
    monkeypatch.setenv("GIT_DIR", str(other / ".git"))
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Evil Env")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "evil@example.org")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.hooksPath")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "/tmp")
    monkeypatch.setenv("EMAIL", "evil@example.org")
    run_apply(env, sha)
    monkeypatch.undo()
    assert "Evil" not in g(env.repo, "log", "-1", "--format=%an %ae %cn %ce") and g(other, "log", "--oneline", check=False) == ""


# ---- locks, crashes and failures in the middle -----------------------------------------------------------------------------------------

def test_two_applies_on_one_repository_and_on_one_job_are_refused_while_one_runs(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    held = env.job()
    with held.lock(), pytest.raises(rj.Refused):
        run_apply(env, sha)
    with ra.lock_repo(env.jobs, env.repo):
        with pytest.raises(rj.Refused, match="another"):
            run_apply(env, sha)
    run_apply(env, sha)


def test_the_repository_lock_is_the_same_for_two_paths_to_one_repository(env, tmp_path):
    link = tmp_path / "link"
    link.symlink_to(env.repo)
    with ra.lock_repo(env.jobs, env.repo):
        with pytest.raises(rj.Refused, match="another"):
            with ra.lock_repo(env.jobs, link):
                pass


def test_a_commit_that_fails_leaves_the_repository_and_the_job_as_they_were(env, tmp_path, monkeypatch):
    patch, sha = package(env, tmp_path, edit_shop())
    before = head(env)
    real = ra.run_git

    def failing(repo, *args, **kw):
        if args and args[0] == "commit":
            raise ra.GitFail("commit refused")
        return real(repo, *args, **kw)
    monkeypatch.setattr(ra, "run_git", failing)
    with pytest.raises(rj.Refused, match="commit"):
        run_apply(env, sha)
    untouched(env, before)


def test_a_crash_after_the_commit_is_healed_by_the_next_call_without_a_second_commit(env, tmp_path, monkeypatch):
    patch, sha = package(env, tmp_path, edit_shop())
    before = head(env)
    real = rj._record_applied

    def crash(*a, **k):
        raise KeyboardInterrupt("killed after the commit")
    monkeypatch.setattr(rj, "_record_applied", crash)
    with pytest.raises(KeyboardInterrupt):
        run_apply(env, sha)
    assert head(env) != before and env.job().data["state"] == rj.REVIEW_READY
    monkeypatch.setattr(rj, "_record_applied", real)
    job = run_apply(env, sha)
    assert job.data["state"] == rj.APPLIED and g(env.repo, "rev-list", "--count", f"{before}..HEAD") == "1"
    assert job.data["log"][-1]["recovered"] is True


def test_changes_left_in_the_tree_by_a_crash_before_the_commit_are_named_not_guessed(env, tmp_path, monkeypatch):
    patch, sha = package(env, tmp_path, edit_shop())
    real = ra.run_git

    def die(repo, *args, **kw):
        if args and args[0] == "commit":
            raise KeyboardInterrupt("killed before the commit")
        return real(repo, *args, **kw)
    monkeypatch.setattr(ra, "run_git", die)
    with pytest.raises(KeyboardInterrupt):
        run_apply(env, sha)
    monkeypatch.setattr(ra, "run_git", real)
    with pytest.raises(rj.Refused, match="apply -R"):
        run_apply(env, sha)


def test_a_patch_that_is_not_what_git_would_write_byte_for_byte_is_undone(env, tmp_path):
    """The patch applies, but its header (an abbreviated index line) is not what the package writes: the staged change differs, so it is refused and undone."""
    scratch = tmp_path / "s2"
    shutil.copytree(env.repo, scratch)
    (scratch / "doc.txt").write_text("one\ntwo\n")
    td.git(scratch, "add", "-A", "-f")
    short = subprocess.run(["git", "-C", str(scratch), "diff", "--cached", "--binary", "--no-renames", "--no-color", "--no-ext-diff"],
                           capture_output=True, check=True).stdout
    patch, sha = rewrite(env, short, [{"path": "doc.txt", "change": "A"}])
    before = head(env)
    with pytest.raises(rj.Refused, match="byte for byte"):
        run_apply(env, sha)
    untouched(env, before)


def test_a_commit_that_is_not_the_patch_is_not_recorded_but_stays_and_is_named(env, tmp_path, monkeypatch):
    patch, sha = package(env, tmp_path, edit_shop())
    before = head(env)
    calls = []

    def patch_id(repo, diff):
        calls.append(1)
        return "same" if len(calls) % 2 else "different"            # the patch's id, then the commit's: they differ
    monkeypatch.setattr(rj, "patch_id", patch_id)
    with pytest.raises(rj.Refused, match="was made and stays.*argus applied"):
        run_apply(env, sha)
    assert head(env) != before and env.job().data["state"] == rj.REVIEW_READY


def test_a_commit_of_another_job_or_another_patch_is_not_taken_for_this_jobs_apply(env, tmp_path, monkeypatch):
    patch, sha = package(env, tmp_path, edit_shop())
    before = head(env)
    real = rj._record_applied
    monkeypatch.setattr(rj, "_record_applied", lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt("killed after the commit")))
    with pytest.raises(KeyboardInterrupt):
        run_apply(env, sha)
    monkeypatch.setattr(rj, "_record_applied", real)
    g(env.repo, "-c", "user.name=t", "-c", "user.email=t@example.org", "commit", "-q", "--amend", "-m", "x\n\nArgus-Job: another\nArgus-Patch-Sha256: " + sha, check=True)
    with pytest.raises(rj.Refused):
        run_apply(env, sha)
    assert env.job().data["state"] == rj.REVIEW_READY and g(env.repo, "rev-list", "--count", f"{before}..HEAD") == "1"


# ---- the review of the first implementation -----------------------------------------------------------------------------------------------

def test_a_job_json_that_does_not_name_the_patch_is_refused_even_when_provenance_does(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    job = env.job()
    job.data["stages"]["a1"]["review"]["patch_sha256"] = "0" * 64
    job.save()
    refused(env, tmp_path, sha, "not the one the review recorded")


def test_the_users_global_git_configuration_is_used_for_the_identity_and_for_nothing_else(env, tmp_path, home):
    marks = {n: tmp_path / f"ran-{n}" for n in ("fsmonitor", "gpg", "filter", "pager")}
    scripts = {}
    for n, mark in marks.items():
        sc = tmp_path / f"{n}.sh"
        sc.write_text(f"#!/bin/sh\ntouch {mark}\ncat\n")
        sc.chmod(0o755)
        scripts[n] = sc
    (home / ".gitconfig").write_text(
        "[user]\n\tname = Global Person\n\temail = global@example.org\n"
        f"[core]\n\tfsmonitor = {scripts['fsmonitor']}\n\tpager = {scripts['pager']}\n"
        f"[commit]\n\tgpgsign = true\n[gpg]\n\tprogram = {scripts['gpg']}\n"
        f"[filter \"x\"]\n\tclean = {scripts['filter']}\n\tsmudge = {scripts['filter']}\n")
    patch, sha = package(env, tmp_path, edit_shop())
    (env.repo / ".git" / "info").mkdir(exist_ok=True)
    (env.repo / ".git" / "info" / "attributes").write_text("*.py filter=x\n")
    for m in marks.values():
        m.unlink(missing_ok=True)
    job = run_apply(env, sha)
    assert job.data["state"] == rj.APPLIED and [n for n, m in marks.items() if m.exists()] == []
    assert g(env.repo, "log", "-1", "--format=%an") == "Global Person"


def test_a_pr_md_that_cannot_be_read_as_a_title_gives_the_fallback_not_a_half_applied_repository(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    d = Path(env.job().data["stages"]["a1"]["review"]["dir"])
    (d / "PR.md").write_bytes(b"# title with a NUL \x00 and bad bytes \xff\xfe\n")
    job = run_apply(env, sha)
    assert job.data["state"] == rj.APPLIED and "\x00" not in g(env.repo, "log", "-1", "--format=%s")
    shutil.rmtree(tmp_path / "s", ignore_errors=True)


def test_a_head_that_moved_while_the_patch_went_in_is_named_and_not_recorded(env, tmp_path, monkeypatch):
    patch, sha = package(env, tmp_path, edit_shop())
    real = ra.run_git
    moved = []

    def racing(repo, *args, **kw):
        if args and args[0] == "apply" and "--index" in args and not moved:
            moved.append(1)
            real(repo, "-c", "user.name=h", "-c", "user.email=h@example.org", "commit", "-q", "--allow-empty", "-m", "a human commit")
        return real(repo, *args, **kw)
    monkeypatch.setattr(ra, "run_git", racing)
    with pytest.raises(rj.Refused, match="HEAD moved"):
        run_apply(env, sha)
    assert env.job().data["state"] == rj.REVIEW_READY


def test_a_failure_after_the_commit_is_not_reported_as_undone_and_is_recorded(env, tmp_path, monkeypatch):
    patch, sha = package(env, tmp_path, edit_shop())
    before = head(env)
    real = ra.run_git
    state = {"committed": False, "failed": False}

    def flaky(repo, *args, **kw):
        out = real(repo, *args, **kw)
        if args and args[0] == "commit":
            state["committed"] = True
        elif args == ("rev-parse", "HEAD") and state["committed"] and not state["failed"]:
            state["failed"] = True
            raise ra.GitFail("rev-parse timed out")
        return out
    monkeypatch.setattr(ra, "run_git", flaky)
    job = run_apply(env, sha)
    assert job.data["state"] == rj.APPLIED and g(env.repo, "rev-list", "--count", f"{before}..HEAD") == "1"


def test_when_even_the_reverse_apply_fails_the_hard_reset_cleans_and_when_nothing_works_the_tree_is_named(env, tmp_path, monkeypatch):
    patch, sha = package(env, tmp_path, edit_shop())
    before = head(env)
    real = ra.run_git

    def broken(repo, *args, **kw):
        if args and args[0] == "commit":
            raise ra.GitFail("commit refused")
        if args[:2] == ("apply", "-R"):
            raise ra.GitFail("reverse refused")
        return real(repo, *args, **kw)
    monkeypatch.setattr(ra, "run_git", broken)
    with pytest.raises(rj.Refused, match="was undone"):
        run_apply(env, sha)
    untouched(env, before)
    def worse(repo, *args, **kw):
        if args and args[0] in ("commit", "reset") or args[:2] == ("apply", "-R"):
            raise ra.GitFail("refused")
        return real(repo, *args, **kw)
    monkeypatch.setattr(ra, "run_git", worse)
    with pytest.raises(rj.Refused, match="THE TREE IS NOT CLEAN"):
        run_apply(env, sha)


def test_a_commit_two_on_from_the_recorded_head_or_with_another_patch_is_not_recovered(env, tmp_path, monkeypatch):
    patch, sha = package(env, tmp_path, edit_shop())
    before = head(env)
    real = rj._record_applied
    monkeypatch.setattr(rj, "_record_applied", lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt("killed after the commit")))
    with pytest.raises(KeyboardInterrupt):
        run_apply(env, sha)
    monkeypatch.setattr(rj, "_record_applied", real)
    mine = head(env)
    g(env.repo, "-c", "user.name=t", "-c", "user.email=t@example.org", "commit", "-q", "--allow-empty", "-m", "someone else, on top")
    with pytest.raises(rj.Refused):
        run_apply(env, sha)                                    # HEAD is two commits on from head_before: not the one this job made
    assert env.job().data["state"] == rj.REVIEW_READY
    g(env.repo, "reset", "-q", "--hard", mine)
    g(env.repo, "-c", "user.name=t", "-c", "user.email=t@example.org", "commit", "-q", "--amend", "-m", "x\n\nArgus-Job: jtest\nArgus-Patch-Sha256: " + "0" * 64)
    with pytest.raises(rj.Refused):
        run_apply(env, sha)                                    # the trailers name another patch
    assert before != head(env)


def link_in_the_base(env):
    """A symlink in the repository's base commit: the job's intake commit is moved to it."""
    os.symlink("src/shop.py", env.repo / "alias")
    g(env.repo, "add", "-A")
    td.git(env.repo, "commit", "-qm", "base with a symlink")
    job = env.job()
    job.data["intake"]["commit"] = head(env)
    job.save()


def test_a_patch_that_changes_a_symlink_that_exists_is_refused(env, tmp_path):
    link_in_the_base(env)
    def change(r):
        (r / "alias").unlink()
        os.symlink("tests/test_old.py", r / "alias")
    patch, sha = package(env, tmp_path, change)
    refused(env, tmp_path, sha, "symlink")


def test_a_patch_that_adds_a_submodule_entry_is_refused(env, tmp_path):
    scratch = tmp_path / "s3"
    shutil.copytree(env.repo, scratch)
    g(scratch, "update-index", "--add", "--cacheinfo", f"160000,{head(env)},sub")
    patch = subprocess.run(["git", "-C", str(scratch), "diff", "--cached", "--binary", "--full-index", "--no-renames", "--no-color", "--no-ext-diff"],
                           capture_output=True, check=True).stdout
    assert b"160000" in patch
    patch, sha = rewrite(env, patch, [{"path": "sub", "change": "A"}])
    refused(env, tmp_path, sha, "symlink or a submodule")


def test_the_cli_prints_the_branch_and_says_it_was_not_pushed(env, tmp_path, capsys):
    sys.path.insert(0, str(tr.ROOT / "scripts"))
    import argus
    patch, sha = package(env, tmp_path, edit_shop())
    branch = g(env.repo, "symbolic-ref", "--short", "HEAD")
    read_ok(env, sha)
    assert argus.main(["--jobs-dir", str(env.jobs), "apply", "jtest", "--read-sha", sha[:12]], deps=env.deps) == 0
    out = capsys.readouterr().out
    assert f"applied on branch {branch}" in out and "not pushed, not deployed" in out and "argus stage deploy jtest" in out


def test_a_repository_whose_git_is_a_file_not_a_directory_is_refused(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    wt = tmp_path / "linked"
    g(env.repo, "worktree", "add", "-q", "-b", "linked-branch", str(wt))
    assert (wt / ".git").is_file()
    job = env.job()
    job.data["inputs"]["repo"] = str(wt)
    job.save()
    with pytest.raises(rj.Refused, match="own .git directory"):
        run_apply(env, sha)
    assert env.job().data["state"] == rj.REVIEW_READY


def test_a_commit_with_this_jobs_trailers_but_another_parent_is_not_recovered(env, tmp_path, monkeypatch):
    patch, sha = package(env, tmp_path, edit_shop())
    before = head(env)
    real = rj._record_applied
    monkeypatch.setattr(rj, "_record_applied", lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt("killed after the commit")))
    with pytest.raises(KeyboardInterrupt):
        run_apply(env, sha)
    monkeypatch.setattr(rj, "_record_applied", real)
    ident = ["-c", "user.name=t", "-c", "user.email=t@example.org"]
    g(env.repo, "reset", "-q", "--hard", before)
    (env.repo / "other.txt").write_text("a human commit in between\n")
    g(env.repo, "add", "-A")
    g(env.repo, *ident, "commit", "-q", "-m", "a human commit")
    p = env.repo.parent / "again.patch"
    p.write_bytes(patch)
    g(env.repo, "apply", "--index", str(p))
    g(env.repo, *ident, "commit", "-q", "-m", f"copy\n\nArgus-Job: jtest\nArgus-Patch-Sha256: {sha}")
    with pytest.raises(rj.Refused):
        run_apply(env, sha)                                   # right trailers, same changes, but not a child of the HEAD the job logged
    assert env.job().data["state"] == rj.REVIEW_READY


def test_a_failure_that_is_not_a_git_failure_after_the_change_is_undone_too(env, tmp_path, monkeypatch):
    patch, sha = package(env, tmp_path, edit_shop())
    before = head(env)
    real = ra.run_git

    def full(repo, *args, **kw):
        if args and args[0] == "commit":
            raise OSError("no space left on device")
        return real(repo, *args, **kw)
    monkeypatch.setattr(ra, "run_git", full)
    with pytest.raises(rj.Refused, match="undone"):
        run_apply(env, sha)
    untouched(env, before)


# ---- SPEC_APPLY_ACCEPT_CONCERNS ---------------------------------------------------------------------------------------------------------

REASON = "the tests sit in a new file, the code is right and 32 tests pass"


def accept(env, sha, reason=REASON, **kw):
    return ra.apply("jtest", sha[:12], deps=env.deps, jobs_dir=env.jobs, accept_concerns=reason, **kw)


def test_accepted_concerns_apply_with_the_trailer_the_log_line_and_the_status(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    read_pair(env, "ok", "concerns")
    before = head(env)
    job = accept(env, sha)
    assert job.data["state"] == rj.APPLIED and head(env) != before
    msg = g(env.repo, "log", "-1", "--format=%B")
    assert msg.endswith(f"Argus-Patch-Sha256: {sha}\nAccepted-concerns: {REASON}")
    e = job.data["log"][-1]
    assert e["accepted_concerns"] == REASON and e["accepted_sha"] == sha and e["accepted_findings"] == [["reader-b", "second reading"]]
    started = [x for x in job.data["log"] if x.get("what") == "apply_started"][-1]
    assert started["accepted_concerns"] == REASON
    assert f"applied with accepted concerns: {REASON}" in rj.status("jtest", jobs_dir=env.jobs)


def test_first_concerns_with_a_valid_second_applies_and_lists_both_findings(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    read_pair(env, "concerns", "concerns")
    job = accept(env, sha)
    assert [f[0] for f in job.data["log"][-1]["accepted_findings"]] == ["reader-a", "reader-b"]


def test_the_plain_commit_message_is_byte_for_byte_as_before(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    run_apply(env, sha)
    assert g(env.repo, "log", "-1", "--format=%B").endswith(f"Argus-Job: jtest\nArgus-Patch-Sha256: {sha}")
    assert "Accepted-concerns" not in g(env.repo, "log", "-1", "--format=%B")
    assert "accepted_concerns" not in env.job().data["log"][-1]
    assert "accepted concerns" not in rj.status("jtest", jobs_dir=env.jobs)


def test_a_concern_without_the_flag_is_refused_as_today(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    read_pair(env, "ok", "concerns")
    before = head(env)
    with pytest.raises(rj.Refused, match="recorded concerns"):
        ra.apply("jtest", sha[:12], deps=env.deps, jobs_dir=env.jobs)
    untouched(env, before)


@pytest.mark.parametrize("reason", ["", "short", "x" * 9, "y" * 501, "a valid length but sk-ant-abcdefgh12345 inside", "a reason\x07 with a bell char",
                                    "a reason with api_key = \"abc\" in it"])
def test_a_bad_reason_is_refused_and_nothing_changes(env, tmp_path, reason):
    patch, sha = package(env, tmp_path, edit_shop())
    read_pair(env, "ok", "concerns")
    before = head(env)
    with pytest.raises(rj.Refused, match="accept-concerns"):
        accept(env, sha, reason)
    untouched(env, before)
    assert not [x for x in env.job().data["log"] if x.get("what") == "apply_started"]


@pytest.mark.parametrize("first,second,why", [
    ("ok", None, "only one"), ("concerns", None, "second patch reading|only one"), ("ok", "ok", "nothing to accept"),
])
def test_only_a_pair_with_a_concern_is_accepted(env, tmp_path, first, second, why):
    patch, sha = package(env, tmp_path, edit_shop())
    read_pair(env, first, second)
    before = head(env)
    with pytest.raises(rj.Refused, match=why):
        accept(env, sha)
    untouched(env, before)


def test_no_note_a_stale_note_and_a_damaged_second_reading_are_refused_with_the_flag(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    before = head(env)
    with pytest.raises(rj.Refused, match="no patch-read note"):
        accept(env, sha)
    read_pair(env, "ok", "concerns")
    f = [p for p in env.job().dir.iterdir() if p.name.startswith("patch_read")]
    assert len(f) == 1
    rec = json.loads(f[0].read_text())
    rec["second"]["note"] = ""
    f[0].write_text(json.dumps(rec))
    with pytest.raises(rj.Refused):
        accept(env, sha)
    untouched(env, before)


def test_the_same_reader_id_twice_is_not_two_readers(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    read_pair(env, "ok", "concerns")
    f = [p for p in env.job().dir.iterdir() if p.name.startswith("patch_read")][0]
    rec = json.loads(f.read_text())
    rec["second"]["reader"]["id"] = rec["reader"]["id"]
    f.write_text(json.dumps(rec))
    before = head(env)
    with pytest.raises(rj.Refused):
        accept(env, sha)
    untouched(env, before)


def test_the_reader_filter_applies_to_both_readings(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    read_pair(env, "ok", "concerns")
    before = head(env)
    with pytest.raises(rj.Refused, match="--reader"):
        accept(env, sha, reader="argus")
    untouched(env, before)


def test_a_sha_of_another_patch_is_refused_with_the_flag(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    read_pair(env, "ok", "concerns")
    before = head(env)
    with pytest.raises(rj.Refused, match="read-sha"):
        ra.apply("jtest", "0" * 12, deps=env.deps, jobs_dir=env.jobs, accept_concerns=REASON)
    untouched(env, before)


def test_the_other_checks_still_refuse_with_the_flag(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    read_pair(env, "ok", "concerns")
    before = head(env)
    (env.repo / "dirty.txt").write_text("x")
    with pytest.raises(rj.Refused, match="not clean"):
        accept(env, sha)
    (env.repo / "dirty.txt").unlink()
    job = env.job()
    job.data["protected_repo"] = {"globs": ["src/*"]}
    job.save()
    with pytest.raises(rj.Refused, match="protects"):
        accept(env, sha)
    untouched(env, before)


def test_the_flag_on_an_applied_job_is_refused(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    read_pair(env, "ok", "concerns")
    accept(env, sha)
    with pytest.raises(rj.Refused, match="APPLIED"):
        accept(env, sha)


def test_a_crash_after_the_commit_needs_the_flag_and_keeps_the_acceptance(env, tmp_path, monkeypatch):
    patch, sha = package(env, tmp_path, edit_shop())
    read_pair(env, "ok", "concerns")
    before = head(env)
    real = rj._record_applied

    def crash(*a, **k):
        raise KeyboardInterrupt("killed after the commit")
    monkeypatch.setattr(rj, "_record_applied", crash)
    with pytest.raises(KeyboardInterrupt):
        accept(env, sha)
    monkeypatch.setattr(rj, "_record_applied", real)
    with pytest.raises(rj.Refused):                                  # without the flag: refused at the reader check, before anything is healed
        ra.apply("jtest", sha[:12], deps=env.deps, jobs_dir=env.jobs)
    job = accept(env, sha)
    assert g(env.repo, "rev-list", "--count", f"{before}..HEAD") == "1"
    e = job.data["log"][-1]
    assert e["recovered"] is True and e["accepted_concerns"] == REASON


def test_the_flag_combines_with_allowed_failed_examples_and_is_recorded_separately(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    read_pair(env, "ok", "concerns")
    job = accept(env, sha, allow_failed_examples=())
    assert "examples_failed" not in job.data["log"][-1] and job.data["log"][-1]["accepted_concerns"] == REASON


def test_the_cli_takes_the_flag(env, tmp_path, capsys):
    sys.path.insert(0, str(tr.ROOT / "scripts"))
    import argus
    patch, sha = package(env, tmp_path, edit_shop())
    read_pair(env, "ok", "concerns")
    assert argus.main(["--jobs-dir", str(env.jobs), "apply", "jtest", "--read-sha", sha[:12], "--accept-concerns", REASON], deps=env.deps) == 0
    assert f"applied with accepted concerns: {REASON}" in capsys.readouterr().out


def edit_note(env, fn):
    f = [p for p in env.job().dir.iterdir() if p.name.startswith("patch_read")][0]
    rec = json.loads(f.read_text())
    fn(rec)
    f.write_text(json.dumps(rec))


@pytest.mark.parametrize("name,fn,kw", [
    ("a second reading of a model under another template", lambda r: r["second"].update(reader={"kind": "argus", "id": "m2"}, template_sha256="0" * 64), {}),
    ("a first reading without an id", lambda r: r["reader"].pop("id"), {}),
    ("a first reading by another kind than --reader", lambda r: r.update(reader={"kind": "argus", "id": "m1"}, template_sha256=pr_template()), {"reader": "claude"}),
])
def test_more_reader_checks_hold_with_the_flag(env, tmp_path, name, fn, kw):
    patch, sha = package(env, tmp_path, edit_shop())
    read_pair(env, "concerns", "concerns")
    edit_note(env, fn)
    before = head(env)
    with pytest.raises(rj.Refused):
        accept(env, sha, **kw)
    untouched(env, before)


def pr_template():
    from router import patch_read as pr
    return pr.TEMPLATE_SHA256
