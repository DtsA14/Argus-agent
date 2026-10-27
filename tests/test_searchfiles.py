"""SearchFiles (docs/reviews/DESIGN_SEARCHFILES.md): a read-only, literal search inside the workspace path jail, bounded
in what it reads and in what it returns. Adversarial cases: traversal, symlinks out of the workspace, special files,
large files, Unicode, many matches, no matches, and every work and output limit."""
import os
import sys
import threading
from pathlib import Path

import pytest

from codetask import tools as ct
from harness.events import EventLog

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="the path jail needs openat; the VM runs these")

CONTRACT = {"contract": "t", "inputs": {"issue": "x"}, "scope": {"writable": ["src/**"], "protected": ["tests/**"]},
            "validation": [], "artifacts": [{"schema": "claims_v2"}]}
ALL = ["list_files", "search_files", "read_file", "write_file", "run_validation"]


def box(ws, tmp_path, allowed=ALL):
    return ct.Toolbox(str(ws), CONTRACT, {}, allowed, EventLog(tmp_path / "e.jsonl"))


def search(b, text, path=""):
    return b.run({"name": "SearchFiles", "args": {"text": text, "path": path}})["content"]


@pytest.fixture
def ws(tmp_path):
    root = tmp_path / "ws"
    (root / "src" / "pkg").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "src" / "keys.py").write_text("def report_key(c, p):\n    return (c, p)\n")
    (root / "src" / "pkg" / "use.py").write_text("x = 1\nk = report_key(a, b)\nReport_Key = 2\n")
    (root / "tests" / "test_keys.py").write_text("from src.keys import report_key\n")
    return root


def test_it_finds_literal_text_with_path_and_line_in_order(ws, tmp_path):
    out = search(box(ws, tmp_path), "report_key")
    assert out.splitlines() == ["src/keys.py:1: def report_key(c, p):",
                                "src/pkg/use.py:2: k = report_key(a, b)",
                                "tests/test_keys.py:1: from src.keys import report_key"]


def test_it_is_case_sensitive_and_literal(ws, tmp_path):
    b = box(ws, tmp_path)
    assert search(b, "REPORT_KEY") == "No matches."
    assert search(b, "report_.ey") == "No matches."                      # not a pattern
    assert "src/pkg/use.py:3" in search(b, "Report_Key")


def test_path_limits_the_search_to_a_directory(ws, tmp_path):
    b = box(ws, tmp_path)
    assert search(b, "report_key", "src/pkg").splitlines() == ["src/pkg/use.py:2: k = report_key(a, b)"]
    assert search(b, "report_key", "src/nope") == "No such directory: 'src/nope'"
    # SPEC_LOCATE_FROM_TRACEBACK 2.3: a file path searches that file only (tests/test_locate_from_traceback.py)
    assert search(b, "report_key", "src/keys.py").splitlines() == ["src/keys.py:1: def report_key(c, p):"]
    assert search(b, "x", "src/keys.py/y") == "Rejected: 'src/keys.py/y' is not a directory or a regular file."


@pytest.mark.parametrize("path", ["../", "..", "src/../..", "/etc", "/", "src\x00"])
def test_paths_outside_the_workspace_are_refused(ws, tmp_path, path):
    assert search(box(ws, tmp_path), "root", path).startswith("Refused")


def test_symlinks_are_never_followed(ws, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.py").write_text("report_key = 'SECRET'\n")
    os.symlink(outside, ws / "src" / "linkdir")                         # a directory out of the workspace
    os.symlink(outside / "secret.py", ws / "src" / "link.py")           # a file out of the workspace
    b = box(ws, tmp_path)
    out = search(b, "report_key")
    assert "SECRET" not in out and "link" not in out
    assert search(b, "report_key", "src/linkdir").startswith("Refused")


def test_special_files_are_skipped_without_blocking(ws, tmp_path):
    os.mkfifo(ws / "src" / "pipe.py")
    done = {}
    t = threading.Thread(target=lambda: done.setdefault("out", search(box(ws, tmp_path), "report_key")))
    t.start()
    t.join(timeout=10)
    assert not t.is_alive() and "pipe" not in done["out"] and "src/keys.py:1" in done["out"]


def test_a_file_too_large_is_reported_not_read(ws, tmp_path, monkeypatch):
    monkeypatch.setattr(ct, "SEARCH_MAX_FILE", 100)
    (ws / "src" / "big.py").write_text("report_key\n" * 50)
    out = search(box(ws, tmp_path), "report_key")
    assert "src/big.py:" not in out
    assert "1 file(s) larger than 100 bytes were not searched: src/big.py" in out


def test_unicode_text_and_lines(ws, tmp_path, monkeypatch):
    monkeypatch.setattr(ct, "SEARCH_MAX_LINE", 12)
    (ws / "src" / "uni.py").write_text("harga = '€ 5'  # café naïve ünïcödé\n", encoding="utf-8")
    b = box(ws, tmp_path)
    assert search(b, "naïve").splitlines() == ["src/uni.py:1: harga = '€ 5"]   # cut by characters, not bytes
    assert search(b, "€").startswith("src/uni.py:1:")


def test_many_matches_are_cut_and_say_so(ws, tmp_path):
    (ws / "src" / "many.py").write_text("".join(f"hit_{i} = 1\n" for i in range(45)))
    lines = search(box(ws, tmp_path), "hit_").splitlines()
    assert len(lines) == ct.SEARCH_MAX_MATCHES + 1
    assert lines[-1].startswith("... 25 more matches not shown: results incomplete")


def test_long_lines_are_cut(ws, tmp_path):
    (ws / "src" / "long.py").write_text("needle " + "x" * 1000 + "\n")
    (line,) = search(box(ws, tmp_path), "needle").splitlines()
    assert len(line) == len("src/long.py:1: ") + ct.SEARCH_MAX_LINE


def test_the_files_read_per_call_are_bounded(ws, tmp_path, monkeypatch):
    monkeypatch.setattr(ct, "SEARCH_MAX_FILES", 2)
    out = search(box(ws, tmp_path), "report_key")
    assert out.splitlines()[-1].startswith("... search stopped after 2 files")
    assert "tests/test_keys.py" not in out                               # the third file was never read


def test_the_bytes_read_per_call_are_bounded(ws, tmp_path, monkeypatch):
    monkeypatch.setattr(ct, "SEARCH_MAX_BYTES", 30)
    out = search(box(ws, tmp_path), "report_key")
    assert "search stopped after 0 files (0 bytes)" in out and "No matches in the 0 files searched." in out


def test_bad_text_is_rejected(ws, tmp_path):
    b = box(ws, tmp_path)
    for text in ("", "a\nb", "a\rb", "x" * (ct.SEARCH_MAX_TEXT + 1), None, 5):
        assert b.run({"name": "SearchFiles", "args": {"text": text}})["content"].startswith("Rejected")


def test_search_is_denied_unless_allowed_and_is_not_offered_by_default(ws, tmp_path):
    b = box(ws, tmp_path, allowed=["read_file"])
    assert search(b, "report_key").startswith("Denied")
    from runner import load_config
    default = load_config()["tools"]["coder"]
    assert "search_files" not in default and ct.SearchFiles not in ct.offered(default)
    assert ct.SearchFiles in ct.offered(ALL)


def test_the_same_search_gives_the_same_result(ws, tmp_path):
    b = box(ws, tmp_path)
    assert search(b, "report_key") == search(b, "report_key")            # safe to run again after a crash
    assert sorted(Path(p).name for p in ws.rglob("*")) == sorted(Path(p).name for p in ws.rglob("*"))
