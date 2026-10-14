"""Phase 2d: path jail for file tools (closes the audit finding: write_file accepted ../escaped.txt)."""
import os

import pytest

from harness.events import EventLog
from tools.fs import PathEscape, PathJail
from tools.registry import ToolGate


@pytest.fixture
def jail(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (tmp_path / "outside").mkdir()
    (tmp_path / "outside" / "secret.txt").write_text("secret")
    return PathJail(root)


@pytest.mark.parametrize("rel", ["a.txt", "sub/dir/b.md", "./c.txt", "x/../d.txt"])
def test_paths_inside_the_root_are_allowed(jail, rel):
    jail.write_text(rel, "ok")
    assert jail.read_text(rel) == "ok"
    assert jail.resolve(rel).is_relative_to(jail.root)


@pytest.mark.parametrize("rel", ["../escaped.txt", "a/../../escaped.txt", "sub/../../../etc/passwd",
                                 "/etc/passwd", "/tmp/x", "", "   ", "a\x00b", ".", "sub/.."])
def test_escapes_and_bad_paths_are_refused(jail, rel):
    with pytest.raises(PathEscape):
        jail.write_text(rel, "x")
    with pytest.raises(PathEscape):
        jail.read_text(rel)


def test_nothing_is_written_outside_on_refusal(jail, tmp_path):
    with pytest.raises(PathEscape):
        jail.write_text("../escaped.txt", "x")
    assert not (tmp_path / "escaped.txt").exists()


def test_symlink_file_pointing_outside_is_refused(jail, tmp_path):
    os.symlink(tmp_path / "outside" / "secret.txt", jail.root / "link.txt")
    with pytest.raises(PathEscape):
        jail.read_text("link.txt")
    with pytest.raises(PathEscape):
        jail.write_text("link.txt", "overwrite")
    assert (tmp_path / "outside" / "secret.txt").read_text() == "secret"


def test_symlink_directory_pointing_outside_is_refused(jail, tmp_path):
    os.symlink(tmp_path / "outside", jail.root / "dir")
    with pytest.raises(PathEscape):
        jail.write_text("dir/new.txt", "x")
    with pytest.raises(PathEscape):
        jail.read_text("dir/secret.txt")
    assert not (tmp_path / "outside" / "new.txt").exists()


def test_symlinks_are_refused_even_when_they_stay_inside_the_root(jail):
    # Stricter since the audit of PR #3 (P2): no symlink is followed at any level, so a link's target
    # never has to be re-checked (and cannot be swapped between check and use).
    jail.write_text("real.txt", "data")
    jail.write_text("realdir/f.txt", "data")
    os.symlink(jail.root / "real.txt", jail.root / "alias.txt")
    os.symlink(jail.root / "realdir", jail.root / "aliasdir")
    for op in (lambda r: jail.read_text(r), lambda r: jail.write_text(r, "x")):
        for rel in ("alias.txt", "aliasdir/f.txt"):
            with pytest.raises(PathEscape):
                op(rel)
    assert jail.read_text("real.txt") == "data" and os.path.islink(jail.root / "alias.txt")


def test_fifo_and_directories_are_not_read(jail):
    os.mkfifo(jail.root / "pipe")                     # opening a FIFO for reading would block forever
    (jail.root / "d").mkdir()
    for rel in ("pipe", "d"):
        with pytest.raises(PathEscape, match="regular"):
            jail.read_text(rel)


def swap_in(stage, rel_dir, target):
    """A race hook: at `stage`, move the real directory away and put a symlink to `target` in its place."""
    def hook(self, at, rel):
        if at == stage:
            d = self.root / rel_dir
            os.rename(d, d.with_name(d.name + "_moved"))
            os.symlink(target, d)
    return hook


def test_file_swapped_for_a_symlink_before_open_is_refused(jail, tmp_path, monkeypatch):
    """TOCTOU on the final component: it was a plain file when validated, a link to outside when opened."""
    jail.write_text("swap.txt", "data")

    def hook(self, at, rel):
        if at == "after_walk":
            (self.root / "swap.txt").unlink()
            os.symlink(tmp_path / "outside" / "secret.txt", self.root / "swap.txt")

    monkeypatch.setattr(PathJail, "_race", hook)
    with pytest.raises(PathEscape):                    # ELOOP from O_NOFOLLOW
        jail.read_text("swap.txt")


@pytest.mark.parametrize("stage", ["before_walk", "after_walk", "before_replace"])
def test_parent_directory_swapped_for_a_symlink_mid_write_never_escapes(jail, tmp_path, monkeypatch, stage):
    """Audit 2d P2: a parent directory replaced by a symlink to outside during the write. Before the
    descriptor walk, this redirected the write outside the root. Now the write is refused (swap before
    the walk) or lands in the directory that was opened (swap after it), never outside."""
    jail.write_text("sub/deep/keep.txt", "old")
    monkeypatch.setattr(PathJail, "_race", swap_in(stage, "sub", tmp_path / "outside"))
    try:
        jail.write_text("sub/deep/new.txt", "x")
    except PathEscape:
        assert stage == "before_walk"
    else:
        assert stage != "before_walk"
        assert (jail.root / "sub_moved" / "deep" / "new.txt").read_text() == "x"
    assert sorted(os.listdir(tmp_path / "outside")) == ["secret.txt"]


@pytest.mark.parametrize("stage", ["before_walk", "after_walk"])
def test_parent_directory_swapped_for_a_symlink_mid_read_never_escapes(jail, tmp_path, monkeypatch, stage):
    jail.write_text("sub/secret.txt", "inside")       # same name as the outside file
    monkeypatch.setattr(PathJail, "_race", swap_in(stage, "sub", tmp_path / "outside"))
    try:
        got = jail.read_text("sub/secret.txt")
    except PathEscape:
        assert stage == "before_walk"
    else:
        assert stage == "after_walk" and got == "inside"   # read from the opened directory, not outside


def test_concurrent_parent_swapping_never_lets_a_write_escape(jail, tmp_path):
    """Real race, no hook: another process keeps flipping root/sub between a directory and a symlink
    to outside while the jail writes into sub/. No write may ever land outside."""
    import subprocess
    import sys
    (jail.root / "sub").mkdir()
    flipper = subprocess.Popen([sys.executable, "-c", """
import os, shutil, sys
d, moved, target = sys.argv[1], sys.argv[1] + "_real", sys.argv[2]
while True:
    try:
        # back to a real directory (the jail may have re-created sub/ in a gap: drop that copy) ...
        if os.path.islink(d):
            os.unlink(d)
        elif os.path.isdir(d) and os.path.isdir(moved):
            shutil.rmtree(d, ignore_errors=True)
        if not os.path.lexists(d) and os.path.isdir(moved):
            os.rename(moved, d)
        # ... then swap it for a symlink to outside
        os.rename(d, moved); os.symlink(target, d)
    except OSError:
        pass
""", str(jail.root / "sub"), str(tmp_path / "outside")])
    import itertools
    import time
    ok = refused = 0
    end = time.monotonic() + 30
    try:
        for i in itertools.count():
            # at least 3000 writes, and keep going until both outcomes were seen (bounded by time)
            if i >= 3000 and (ok and refused or time.monotonic() > end):
                break
            try:
                jail.write_text(f"sub/f{i}.txt", "x")
                ok += 1
            except (PathEscape, OSError):                  # refused, or lost the race: both fine
                refused += 1
    finally:
        flipper.kill(); flipper.wait()
    assert sorted(os.listdir(tmp_path / "outside")) == ["secret.txt"]
    assert ok > 0 and refused > 0                       # the race really happened both ways


def test_write_is_atomic_and_safe_to_repeat(jail):
    jail.write_text("r.md", "v1")
    jail.write_text("r.md", "v2")
    jail.write_text("r.md", "v2")            # same write again, e.g. after a crash
    assert jail.read_text("r.md") == "v2"
    assert sorted(p.name for p in jail.root.iterdir()) == ["r.md"]   # no temp files left


def test_write_file_tool_goes_through_the_jail(tmp_path):
    gate = ToolGate("orchestrator", ["write_file"], EventLog(tmp_path / "e.jsonl"))
    (tmp_path / "run").mkdir()
    gate.call("write_file", str(tmp_path / "run"), "laporan.md", "ok")
    with pytest.raises(PathEscape):
        gate.call("write_file", str(tmp_path / "run"), "../escaped.txt", "x")
    assert not (tmp_path / "escaped.txt").exists()
