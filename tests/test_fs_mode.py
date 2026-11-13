"""Editing a file keeps its permission bits (a file tool wrote a temp file with 0o644 and renamed it over the target, so an edited
executable lost its bit: every more-itertools patch of the outside experiments carried `old mode 100755 / new mode 100644` for
more_itertools/more.py, an unrelated change in the patch a human applies)."""
import os
import stat
import sys
from pathlib import Path

import pytest

from codetask import review
from codetask import tools as tl
from tools.fs import PathEscape, PathJail

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")


def mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


@pytest.fixture
def jail(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    return PathJail(root)


@pytest.mark.parametrize("bits", [0o755, 0o700, 0o600, 0o444, 0o664, 0o751])
def test_a_rewritten_file_keeps_its_permission_bits(jail, bits):
    p = jail.root / "f.py"
    p.write_text("old\n")
    os.chmod(p, bits)
    jail.write_text("f.py", "new\n")
    assert p.read_text() == "new\n" and mode(p) == bits


def test_a_new_file_gets_the_default_mode_and_a_new_file_in_a_new_directory_too(jail):
    jail.write_text("n.py", "x\n")
    jail.write_text("sub/dir/m.py", "y\n")
    assert mode(jail.root / "n.py") == 0o644 and mode(jail.root / "sub/dir/m.py") == 0o644


@pytest.mark.parametrize("special", [0o4755, 0o2755, 0o1755])
def test_setuid_setgid_and_sticky_are_never_carried_over(jail, special):
    p = jail.root / "s.py"
    p.write_text("old\n")
    os.chmod(p, special)
    jail.write_text("s.py", "new\n")
    assert mode(p) == 0o755 and not os.stat(p).st_mode & (stat.S_ISUID | stat.S_ISGID | stat.S_ISVTX)


def test_a_symlink_is_still_refused_and_its_target_untouched(jail, tmp_path):
    target = tmp_path / "outside.txt"
    target.write_text("secret\n")
    os.chmod(target, 0o755)
    os.symlink(target, jail.root / "link.py")
    with pytest.raises(PathEscape):
        jail.write_text("link.py", "x\n")
    assert target.read_text() == "secret\n" and mode(target) == 0o755


def test_no_temporary_file_is_left_behind(jail):
    (jail.root / "f.py").write_text("old\n")
    os.chmod(jail.root / "f.py", 0o755)
    jail.write_text("f.py", "new\n")
    assert sorted(p.name for p in jail.root.iterdir()) == ["f.py"]


# ---- through the agent's tools and into the review patch ----------------------------------------------------------------

CONTRACT = {"scope": {"writable": ["src/**"], "protected": ["tests/**"]},
            "artifacts": [{"path": "SUMMARY.json", "type": "json", "schema": "claims_v2"}]}


class _Log:
    def emit(self, *a, **k):
        pass


def box(root):
    return tl.Toolbox(str(root), CONTRACT, {}, {"write_file", "edit_file", "read_file"}, _Log(),
                      journal=Path(root).parent / "journal.jsonl")


@pytest.fixture
def tree(tmp_path):
    base = tmp_path / "base"
    (base / "src").mkdir(parents=True)
    (base / "src" / "run.py").write_text("def f():\n    return 1\n")
    os.chmod(base / "src" / "run.py", 0o755)
    (base / "src" / "plain.py").write_text("X = 1\n")
    import shutil
    ws = tmp_path / "ws"
    shutil.copytree(base, ws)
    return base, ws


def test_write_file_and_edit_file_keep_the_executable_bit(tree):
    base, ws = tree
    t = box(ws)
    out = t.run({"name": "WriteFile", "args": {"path": "src/run.py", "content": "def f():\n    return 2\n"}})
    assert "Refused" not in out["content"] and mode(ws / "src" / "run.py") == 0o755
    out = t.run({"name": "EditFile", "args": {"path": "src/run.py", "old_text": "return 2", "new_text": "return 3"}}, step_key="k1")
    assert (ws / "src" / "run.py").read_text() == "def f():\n    return 3\n" and mode(ws / "src" / "run.py") == 0o755
    before = mode(ws / "src" / "plain.py")                 # whatever it was (the umask of the machine), it stays
    t.run({"name": "WriteFile", "args": {"path": "src/plain.py", "content": "X = 2\n"}})
    assert (ws / "src" / "plain.py").read_text() == "X = 2\n" and mode(ws / "src" / "plain.py") == before


def test_the_review_patch_of_an_edited_executable_has_no_mode_change(tree, tmp_path):
    base, ws = tree
    box(ws).run({"name": "WriteFile", "args": {"path": "src/run.py", "content": "def f():\n    return 2\n"}})
    patch = review.make_patch(base, ws, tmp_path / "work")
    text = patch if isinstance(patch, str) else patch[0] if isinstance(patch, tuple) else str(patch)
    assert "src/run.py" in text and "old mode" not in text and "new mode" not in text
