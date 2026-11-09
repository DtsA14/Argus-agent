"""scripts/verify_at.sh (verify.sh on one commit in its own worktree) and the verdict line of scripts/verify.sh. The
worktree runs are on a throwaway git repository whose scripts/verify.sh is a stub that records what it saw."""
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
GIT_ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@x", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
STUB = """#!/usr/bin/env bash
set -e
mkdir -p verification
log=verification/verify-20990101T000000Z-test.log
{
  echo "RESULT: PASS"                        # a step before pytest prints its own, as check_env_image.py does
  echo "head: $(git rev-parse HEAD)"
  echo "pin: $(cat .sandbox_image 2>/dev/null || echo none)"
  echo "dirty: $([ -e dirty.txt ] && echo seen || echo absent)"
  echo "cwd: $PWD"
  [ "${STUB_NOLOG:-0}" = 1 ] || echo "$STUB_RESULT"
} > "$log"
[ "${STUB_NOLOG:-0}" = 1 ] && rm -f "$log"
exit 0
"""


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True,
                          env=GIT_ENV).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    (r / "scripts").mkdir(parents=True)
    (r / "scripts" / "verify.sh").write_text(STUB)
    (r / ".gitignore").write_text(".sandbox_image*\n")
    (r / "verification").mkdir()
    for i in range(300):                                        # the commit's own old logs, as Argus-agent has
        (r / "verification" / f"verify-2026010{i % 9 + 1}T{i:06d}Z-old.log").write_text("RESULT: PASS\n")
    git(tmp_path, "init", "-q", str(r))
    git(r, "add", "-A")
    git(r, "commit", "-qm", "base")
    (r / ".sandbox_image").write_text("sha256:abc\n")          # a local pin, ignored by git
    (r / "dirty.txt").write_text("not committed\n")            # the main checkout's own state
    return r


def run(repo, tmp_path, result="RESULT: PASS", **env):
    base = tmp_path / "wts"
    base.mkdir(exist_ok=True)
    return subprocess.run(["bash", str(ROOT / "scripts" / "verify_at.sh"), "HEAD", str(base)], cwd=repo,
                          capture_output=True, text=True, env={**GIT_ENV, "STUB_RESULT": result, **env}, timeout=120)


def test_it_verifies_the_commit_in_its_own_worktree_with_the_pins_and_copies_the_evidence(repo, tmp_path):
    r = run(repo, tmp_path)
    assert r.returncode == 0, (r.stdout[-500:], r.stderr[-500:])
    (log,) = (repo / "verification").glob("verify-2099*.log")      # the new one, among 300 the commit holds
    text = log.read_text()
    assert f"head: {git(repo, 'rev-parse', 'HEAD')}" in text and "pin: sha256:abc" in text
    assert "dirty: absent" in text                             # only the commit, never the checkout's own files
    assert f"cwd: {repo}" not in text and "cwd: " + str(tmp_path / "wts") in text


@pytest.mark.parametrize("result", ["RESULT: FAIL (pytest exit 1)",
                                    "RESULT: FAIL (sandbox tests skipped: 59; set ARGUS_SANDBOX_IMAGE)"])
def test_a_failed_verify_fails_even_after_an_earlier_pass_line(repo, tmp_path, result):
    r = run(repo, tmp_path, result)
    assert r.returncode != 0
    assert list((repo / "verification").glob("verify-2099*.log"))


def test_no_new_log_is_a_failure_even_with_old_ones(repo, tmp_path):
    r = run(repo, tmp_path, STUB_NOLOG="1")
    assert r.returncode != 0 and "wrote 0 new logs" in r.stderr


@pytest.mark.parametrize("result", ["RESULT: PASS", "RESULT: FAIL (x)"])
def test_the_worktree_is_always_removed(repo, tmp_path, result):
    run(repo, tmp_path, result)
    assert list((tmp_path / "wts").iterdir()) == []
    assert len(git(repo, "worktree", "list").splitlines()) == 1


@pytest.mark.parametrize("lines, ok", [
    (["RESULT: PASS", "RESULT: FAIL (pytest exit 1)"], False),            # the bug: an earlier step's PASS line
    (["RESULT: FAIL (x)", "RESULT: PASS"], True),
    (["RESULT: PASS (sandbox NOT verified: 3 skipped, ARGUS_SANDBOX_OPTIONAL=1)"], True),
    (["no verdict"], False),
])
def test_verify_sh_judges_by_its_last_result_line(tmp_path, lines, ok):
    last = [ln for ln in (ROOT / "scripts" / "verify.sh").read_text().splitlines() if ln.strip()][-1]
    log = tmp_path / "v.log"
    log.write_text("\n".join(["== pytest", *lines, "evidence"]) + "\n")
    r = subprocess.run(["bash", "-c", last], env={**os.environ, "LOG": str(log)}, capture_output=True)
    assert (r.returncode == 0) == ok
