"""M6 W4: intake of one commit of a git repository as an input repository, its record, and the check that the input
is still exactly that commit. Builds small git repositories in tmp_path (needs git on the machine; no network)."""
import json
import os
import subprocess
import sys

import pytest

from acceptance import intake

POSIX = pytest.mark.skipif(sys.platform == "win32", reason="executable bits and symlinks: the VM runs these")


def git(repo, *args):
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@x", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env,
                          text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "src_repo"
    (r / "pkg").mkdir(parents=True)
    (r / "verification").mkdir()
    (r / "pkg" / "mod.py").write_text("X = 1\n")
    (r / "pkg" / "data.bin").write_bytes(bytes(range(256)))
    (r / "verification" / "big.log").write_text("evidence\n")
    (r / "README.md").write_bytes(b"crlf\r\nkept as committed\r\n")
    # rules git archive would apply; the intake must ignore them and keep the commit's bytes
    (r / ".gitattributes").write_text("README.md export-subst\npkg/data.bin export-ignore\n")
    git(tmp_path, "init", "-q", str(r))
    git(r, "add", "-A")
    git(r, "commit", "-qm", "first")
    return r


@pytest.fixture
def root(tmp_path):
    (tmp_path / "proj").mkdir()
    return tmp_path / "proj"


def head(r):
    return git(r, "rev-parse", "HEAD")


def test_intake_writes_the_commits_tree_and_a_record_outside_the_workspace(repo, root):
    rec = intake.intake(repo, "HEAD", "demo", exclude=["verification"], root=root)
    ws = root / "fixtures" / "repos" / "demo"
    assert sorted(p.relative_to(ws).as_posix() for p in ws.rglob("*") if p.is_file()) == \
        [".gitattributes", "README.md", "pkg/data.bin", "pkg/mod.py"]
    assert (ws / "README.md").read_bytes() == b"crlf\r\nkept as committed\r\n"      # no attribute rewrote it
    assert (ws / "pkg" / "data.bin").read_bytes() == bytes(range(256))               # export-ignore did not apply
    assert rec["commit"] == head(repo) and rec["tree"] == git(repo, "rev-parse", "HEAD^{tree}")
    assert rec["exclude"] == ["verification"] and rec["files"] == 4
    assert json.loads((root / "fixtures" / "intake" / "demo.json").read_text()) == rec
    assert not list((root / "fixtures" / "repos").glob(".intake-*"))                 # no staging left behind


def test_a_fresh_intake_checks_clean_against_its_record_and_the_repository(repo, root):
    rec = intake.intake(repo, "HEAD", "demo", exclude=["verification"], root=root)
    ws = root / "fixtures" / "repos" / "demo"
    assert intake.check(rec, ws) == [] and intake.check_against_repo(rec, ws, repo) == []
    assert intake.record_for("fixtures/repos/demo", root) == rec


@pytest.mark.parametrize("change", ["modify", "add", "remove", "add_in_new_dir"])
def test_any_change_to_the_snapshot_after_intake_is_detected(repo, root, change):
    rec = intake.intake(repo, "HEAD", "demo", root=root)
    ws = root / "fixtures" / "repos" / "demo"
    if change == "modify":
        (ws / "pkg" / "mod.py").write_text("X = 2\n")
    elif change == "add":
        (ws / "pkg" / "extra.py").write_text("")
    elif change == "remove":
        (ws / "README.md").unlink()
    else:
        (ws / "new").mkdir()
        (ws / "new" / "f.py").write_text("y")
    assert intake.check(rec, ws) and intake.check_against_repo(rec, ws, repo)


def test_bytecode_caches_are_not_part_of_the_snapshot(repo, root):
    rec = intake.intake(repo, "HEAD", "demo", root=root)
    ws = root / "fixtures" / "repos" / "demo"
    (ws / "pkg" / "__pycache__").mkdir()
    (ws / "pkg" / "__pycache__" / "mod.cpython-312.pyc").write_bytes(b"x")
    assert intake.check(rec, ws) == []          # workspaces never contain them (acceptance/workspace.prepare)


def test_a_later_commit_is_not_the_intake(repo, root):
    rec = intake.intake(repo, "HEAD", "demo", root=root)
    (repo / "pkg" / "mod.py").write_text("X = 3\n")
    git(repo, "commit", "-qam", "second")
    ws = root / "fixtures" / "repos" / "demo"
    assert intake.check_against_repo(rec, ws, repo) == []          # still the recorded commit, not HEAD
    assert rec["commit"] != head(repo)


@POSIX
def test_executable_bits_are_kept_and_checked(repo, root):
    (repo / "run.sh").write_text("#!/bin/sh\n")
    os.chmod(repo / "run.sh", 0o755)
    git(repo, "add", "run.sh")
    git(repo, "commit", "-qm", "exec")
    rec = intake.intake(repo, "HEAD", "demo", root=root)
    ws = root / "fixtures" / "repos" / "demo"
    assert rec["executable"] == ["run.sh"] and os.stat(ws / "run.sh").st_mode & 0o111
    os.chmod(ws / "pkg" / "mod.py", 0o755)
    assert "executable bits differ from the intake" in intake.check(rec, ws)


@POSIX
def test_a_symlink_in_the_commit_is_refused_unless_excluded(repo, root):
    os.symlink("pkg/mod.py", repo / "link.py")
    git(repo, "add", "link.py")
    git(repo, "commit", "-qm", "link")
    with pytest.raises(intake.IntakeError, match="not regular files"):
        intake.intake(repo, "HEAD", "demo", root=root)
    assert not (root / "fixtures" / "repos" / "demo").exists() and not (root / "fixtures" / "intake").exists()
    assert intake.intake(repo, "HEAD", "demo", exclude=["link.py"], root=root)["files"] == 5


@pytest.mark.parametrize("kwargs, why", [
    ({"name": "Demo"}, "lower-case name"),
    ({"name": "../demo"}, "lower-case name"),
    ({"exclude": ["../x"]}, "plain relative paths"),
    ({"exclude": ["/etc"]}, "plain relative paths"),
    ({"exclude": ["nothing_here"]}, "matches nothing"),
    ({"commit": "no-such-commit"}, "rev-parse"),
])
def test_bad_intakes_are_refused_and_leave_nothing(repo, root, kwargs, why):
    args = {"name": "demo", "commit": "HEAD", "exclude": [], **kwargs}
    with pytest.raises(intake.IntakeError, match=why):
        intake.intake(repo, args["commit"], args["name"], exclude=args["exclude"], root=root)
    assert not (root / "fixtures" / "intake").exists()
    assert not [p for p in (root / "fixtures" / "repos").glob("*")] if (root / "fixtures" / "repos").exists() else True


def test_intake_never_overwrites(repo, root):
    intake.intake(repo, "HEAD", "demo", root=root)
    with pytest.raises(intake.IntakeError, match="never overwrites"):
        intake.intake(repo, "HEAD", "demo", root=root)


def test_the_remote_url_is_recorded_without_credentials(repo, root):
    git(repo, "remote", "add", "origin", "https://user:ghp_secret@github.com/owner/repo.git")
    rec = intake.intake(repo, "HEAD", "demo", root=root)
    assert rec["repo"] == "https://github.com/owner/repo.git" and "secret" not in json.dumps(rec)


def test_only_a_plain_fixture_workspace_has_a_record(root):
    assert intake.record_for("fixtures/repos/calc", root) is None            # hand-written fixtures have none
    assert intake.record_for("fixtures/repos/a/b", root) is None
