"""scripts/provenance.sh: the verify.sh log names the commit it verified and says whether the tree was clean.

Each test copies the script into a throwaway git repo, so the result does not depend on the state of
this checkout.
"""
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "provenance.sh"


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout


def make_repo(tmp_path):
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    shutil.copy(SCRIPT, repo / "scripts" / "provenance.sh")
    (repo / "app.py").write_text("x = 1\n")
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "t")
    git(repo, "config", "core.autocrlf", "false")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "init")
    return repo


def provenance(repo, *excludes):
    env = {**os.environ, "GIT_CEILING_DIRECTORIES": str(repo.parent)}
    r = subprocess.run(["bash", str(repo / "scripts" / "provenance.sh"), *excludes],
                       capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    return r.stdout.splitlines()


def test_clean_tree_reports_the_exact_head_commit(tmp_path):
    repo = make_repo(tmp_path)
    head = git(repo, "rev-parse", "HEAD").strip()
    assert provenance(repo) == [f"commit: {head}", "working tree: clean"]


def test_modified_and_untracked_files_make_the_tree_dirty_and_are_listed(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "app.py").write_text("x = 2\n")
    (repo / "pkg").mkdir()
    (repo / "pkg" / "new.py").write_text("y = 1\n")  # untracked, inside a new directory
    out = provenance(repo)
    assert out[1] == "working tree: DIRTY (2 paths)"
    assert out[2] == "== git status --porcelain"
    assert sorted(out[3:]) == [" M app.py", "?? pkg/new.py"]


def test_excluded_path_does_not_make_the_tree_dirty(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "verification").mkdir()
    (repo / "verification" / "verify-now.log").write_text("being written\n")
    assert provenance(repo, "verification/verify-now.log")[1] == "working tree: clean"
    (repo / "verification" / "other.log").write_text("not excluded\n")
    out = provenance(repo, "verification/verify-now.log")
    assert out[1] == "working tree: DIRTY (1 paths)" and out[3:] == ["?? verification/other.log"]


def test_outside_a_git_checkout_says_so_instead_of_failing(tmp_path):
    plain = tmp_path / "plain"
    (plain / "scripts").mkdir(parents=True)
    shutil.copy(SCRIPT, plain / "scripts" / "provenance.sh")
    assert provenance(plain) == ["commit: <not a git checkout>"]


def test_verify_sh_records_provenance_and_excludes_its_own_log():
    text = (ROOT / "scripts" / "verify.sh").read_text()
    call = 'bash scripts/provenance.sh "$LOG"'
    assert call in text
    # it must run inside the block that is tee'd to the log, after LOG is set
    assert text.index('LOG="verification/') < text.index(call) < text.index('} 2>&1 | tee "$LOG"')
