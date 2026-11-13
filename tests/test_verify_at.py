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
if [ "${STUB_ESCAPE2:-0}" = 1 ]; then       # a GRANDchild that left the group: only the walk down the whole tree finds it
  bash -c 'setsid sleep 604 & echo $! > "$STUB_PIDFILE"; wait' &
  echo ready > "$STUB_READY"
  wait
fi
if [ "${STUB_SPAWNER:-0}" = 1 ]; then       # keeps starting children for a while: the ones that come after the script took its list
  echo ready > "$STUB_READY"
  for _ in 1 2 3 4 5 6; do sleep 607 & echo $! >> "$STUB_PIDFILE"; sleep 0.3; done
  wait
fi
if [ "${STUB_ESCAPE:-0}" = 1 ]; then        # a process that left the process group of verify.sh (its own session): only the tree reaches it
  setsid sleep 603 & echo $! > "$STUB_PIDFILE"
  echo ready > "$STUB_READY"
  wait
fi
if [ "${STUB_RACE:-0}" = 1 ]; then          # a step that fails under the signal, then the script goes on and starts the next one
  set +e
  echo ready > "$STUB_READY"
  sleep 600 | cat
  sleep 601 & echo $! > "$STUB_PIDFILE"
  wait
fi
if [ "${STUB_HANG:-0}" = 1 ]; then          # a pytest controller with workers: children that outlive their parent unless killed
  bash -c 'sleep 600 & echo $! > "$STUB_PIDFILE"; wait' &
  echo ready > "$STUB_READY"
  wait
fi
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


def default_sigint():
    """A run started in the background (`nohup ... &`) has SIGINT ignored, and so do its children: bash cannot trap a signal that
    was ignored when it started, so the script under test would never see the INT. The script is started with the default."""
    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


@pytest.mark.parametrize("mode", ["STUB_ESCAPE", "STUB_ESCAPE2"])
def test_a_process_that_left_the_process_group_is_killed_through_the_tree(repo, tmp_path, mode):
    import signal
    import time
    base = tmp_path / "wts"
    base.mkdir()
    pidfile, ready = tmp_path / "escaped.pid", tmp_path / "ready"
    p = subprocess.Popen(["bash", str(ROOT / "scripts" / "verify_at.sh"), "HEAD", str(base)], cwd=repo, text=True,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True, preexec_fn=default_sigint,
                         env={**GIT_ENV, "STUB_RESULT": "RESULT: PASS", mode: "1", "STUB_PIDFILE": str(pidfile),
                              "STUB_READY": str(ready)})
    try:
        deadline = time.monotonic() + 30
        while not (ready.exists() and pidfile.exists()) and time.monotonic() < deadline:
            time.sleep(0.1)
        assert ready.exists() and pidfile.exists(), "the stub did not start"
        child = int(pidfile.read_text())
        assert alive(child) and os.getpgid(child) != os.getpgid(p.pid)
        os.kill(p.pid, signal.SIGTERM)
        p.wait(timeout=30)
        deadline = time.monotonic() + 10
        while alive(child) and time.monotonic() < deadline:
            time.sleep(0.1)
        assert not alive(child), "a process outside the group survived the signal"
    finally:
        if pidfile.exists() and alive(int(pidfile.read_text())):
            os.killpg(os.getpgid(int(pidfile.read_text())), signal.SIGKILL)
        if p.poll() is None:
            os.killpg(p.pid, signal.SIGKILL)


def test_children_started_after_the_script_listed_the_tree_are_killed_with_the_group(repo, tmp_path):
    """The script lists the descendants first, then kills: a child started in between is in no list. A slow pgrep (a shim on the
    PATH) makes that window a second long; only the kill of the whole process group reaches the late children."""
    import shutil
    import signal
    import time
    shim = tmp_path / "shim"
    shim.mkdir()
    (shim / "pgrep").write_text(f'#!/usr/bin/env bash\nout="$({shutil.which("pgrep")} "$@")"\nsleep 0.5\nprintf "%s\\n" "$out"\n')
    (shim / "pgrep").chmod(0o755)
    base = tmp_path / "wts"
    base.mkdir()
    pidfile, ready = tmp_path / "spawned.pid", tmp_path / "ready"
    p = subprocess.Popen(["bash", str(ROOT / "scripts" / "verify_at.sh"), "HEAD", str(base)], cwd=repo, text=True,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True, preexec_fn=default_sigint,
                         env={**GIT_ENV, "PATH": f"{shim}:{os.environ['PATH']}", "STUB_RESULT": "RESULT: PASS", "STUB_SPAWNER": "1",
                              "STUB_PIDFILE": str(pidfile), "STUB_READY": str(ready)})
    pids = []
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and not (ready.exists() and pidfile.exists() and len(pidfile.read_text().split()) >= 2):
            time.sleep(0.05)
        assert ready.exists() and pidfile.exists(), "the stub did not start"
        os.kill(p.pid, signal.SIGTERM)
        p.wait(timeout=60)
        time.sleep(1.0)
        pids = [int(x) for x in pidfile.read_text().split()]
        assert len(pids) >= 5, pids                                   # some of them came after the list was taken
        assert [x for x in pids if alive(x)] == [], "children started after the list was taken survived the signal"
    finally:
        for x in pids:
            if alive(x):
                os.kill(x, signal.SIGKILL)
        if p.poll() is None:
            os.killpg(p.pid, signal.SIGKILL)


def test_a_step_started_after_a_child_was_killed_does_not_survive_the_signal(repo, tmp_path):
    import signal
    import time
    base = tmp_path / "wts"
    base.mkdir()
    pidfile, ready = tmp_path / "next.pid", tmp_path / "ready"
    p = subprocess.Popen(["bash", str(ROOT / "scripts" / "verify_at.sh"), "HEAD", str(base)], cwd=repo, text=True,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True, preexec_fn=default_sigint,
                         env={**GIT_ENV, "STUB_RESULT": "RESULT: PASS", "STUB_RACE": "1", "STUB_PIDFILE": str(pidfile),
                              "STUB_READY": str(ready)})
    try:
        deadline = time.monotonic() + 30
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.1)
        assert ready.exists(), "the stub did not start"
        time.sleep(0.5)                                          # inside `sleep 600 | cat`
        os.kill(p.pid, signal.SIGTERM)
        p.wait(timeout=30)
        time.sleep(1.0)
        if pidfile.exists():                                     # the script went on and started the next step: it must be dead
            nxt = int(pidfile.read_text())
            try:
                assert not alive(nxt), "a step started after the first child died survived the signal"
            finally:
                if alive(nxt):
                    os.kill(nxt, signal.SIGKILL)
    finally:
        if pidfile.exists() and alive(int(pidfile.read_text())):          # never leave a sleep behind, whatever failed
            os.kill(int(pidfile.read_text()), signal.SIGKILL)
        if p.poll() is None:
            os.killpg(p.pid, signal.SIGKILL)


@pytest.mark.parametrize("sig", ["TERM", "INT"])
def test_a_signal_kills_the_whole_verify_tree_before_the_worktree_goes(repo, tmp_path, sig):
    import signal
    import time
    base = tmp_path / "wts"
    base.mkdir()
    pidfile, ready = tmp_path / "child.pid", tmp_path / "ready"
    outer = signal.signal(signal.SIGINT, signal.SIG_IGN)          # as in a run started with `nohup ... &`: the child must still get INT
    p = subprocess.Popen(["bash", str(ROOT / "scripts" / "verify_at.sh"), "HEAD", str(base)], cwd=repo, text=True,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True, preexec_fn=default_sigint,
                         env={**GIT_ENV, "STUB_RESULT": "RESULT: PASS", "STUB_HANG": "1", "STUB_PIDFILE": str(pidfile),
                              "STUB_READY": str(ready)})
    try:
        deadline = time.monotonic() + 30
        while not (ready.exists() and pidfile.exists()) and time.monotonic() < deadline:
            time.sleep(0.1)
        assert ready.exists() and pidfile.exists(), "the stub did not start"
        child = int(pidfile.read_text())
        assert alive(child)
        os.kill(p.pid, getattr(signal, "SIG" + sig))
        p.wait(timeout=30)
        assert p.returncode != 0
        deadline = time.monotonic() + 10
        while alive(child) and time.monotonic() < deadline:
            time.sleep(0.1)
        assert not alive(child), "a child of verify.sh survived the signal"
        assert list(base.iterdir()) == []                         # and the worktree is gone
        assert len(git(repo, "worktree", "list").splitlines()) == 1
    finally:
        signal.signal(signal.SIGINT, outer)
        if pidfile.exists() and alive(int(pidfile.read_text())):          # never leave a sleep behind, whatever failed
            os.killpg(os.getpgid(int(pidfile.read_text())), signal.SIGKILL)
        if p.poll() is None:
            os.killpg(p.pid, signal.SIGKILL)
