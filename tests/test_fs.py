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


def test_symlink_that_stays_inside_the_root_is_allowed(jail):
    jail.write_text("real.txt", "data")
    os.symlink(jail.root / "real.txt", jail.root / "alias.txt")
    assert jail.read_text("alias.txt") == "data"   # resolves inside the root: fine


def test_file_swapped_for_a_symlink_after_the_check_is_refused(jail, tmp_path, monkeypatch):
    """TOCTOU: resolve() saw a plain file, then it was replaced by a link to outside before opening.
    The open uses O_NOFOLLOW on the resolved path, so the swapped-in symlink is refused."""
    jail.write_text("swap.txt", "data")
    real_resolve = PathJail.resolve

    def resolve_then_swap(self, rel):
        target = real_resolve(self, rel)
        target.unlink()
        os.symlink(tmp_path / "outside" / "secret.txt", target)
        return target

    monkeypatch.setattr(PathJail, "resolve", resolve_then_swap)
    with pytest.raises(OSError):                       # ELOOP from O_NOFOLLOW
        jail.read_text("swap.txt")


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
