"""ReadFile of a large file without a range shows an outline (fast lane, after argus-ledger 010 and 010b): six attempts
ended at context_limit, each having read whole files of 21,000-34,000 characters (the drafted test file, ledger/api.py,
older test files) that MAX_READ (100,000) let through whole; the first attempt of 010b ran out after 5 reading steps
without writing. A Python file over READ_WHOLE_MAX read without a range now shows its classes and functions with
their lines; another file shows its first part. An attempt that ran out of context after writing is told to start
from the validations."""
import sys
from pathlib import Path

import pytest

from codetask import agent as ag
from codetask import tools as ct
from harness.events import EventLog

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="the path jail needs openat; the VM runs these")

FIX = Path(__file__).resolve().parent.parent / "fixtures" / "feedback" / "ledger_010b"
CONTRACT = {"contract": "t", "inputs": {"issue": "x"}, "scope": {"writable": ["ledger/**"], "protected": ["tests/**"]},
            "validation": [], "artifacts": [{"schema": "claims_v2"}]}
ALL = ["list_files", "search_files", "read_file", "write_file", "run_validation"]
REVOCATION_TESTS = (FIX / "test_session_revocation.py.txt").read_text(encoding="utf-8")
API = (FIX / "api.py.txt").read_text(encoding="utf-8")


def read(ws, tmp_path, path, **kw):
    b = ct.Toolbox(str(ws), CONTRACT, {}, ALL, EventLog(tmp_path / "e.jsonl"))
    return b.run({"name": "ReadFile", "args": {"path": path, **kw}})["content"]


@pytest.fixture
def ws(tmp_path):
    w = tmp_path / "ws"
    (w / "tests").mkdir(parents=True)
    (w / "ledger").mkdir()
    (w / "tests" / "test_session_revocation.py").write_text(REVOCATION_TESTS)
    (w / "ledger" / "api.py").write_text(API)
    (w / "ledger" / "small.py").write_text("def f():\n    return 1\n")
    (w / "README.md").write_text("".join(f"Line {n} of the readme, with some words in it.\n" for n in range(1, 801)))
    (w / "ledger" / "broken.py").write_text("def f(:\n" + "x = 1\n" * 4000)
    (w / "ledger" / "flat.py").write_text("".join(f"value_{n} = {n}\n" for n in range(4000)))
    return w


def test_the_real_drafted_test_file_is_shown_as_an_outline_of_every_test(ws, tmp_path):
    limit = getattr(ct, "READ_WHOLE_MAX", None)
    assert limit and len(REVOCATION_TESTS) > limit, "codetask.tools.READ_WHOLE_MAX: the largest whole read"
    out = read(ws, tmp_path, "tests/test_session_revocation.py")
    lines = len(REVOCATION_TESTS.splitlines())
    assert out.startswith(f"[tests/test_session_revocation.py: {lines} lines, {len(REVOCATION_TESTS)} characters")
    assert "start_line" in out.splitlines()[0]
    tests = [n for n in ("test_a_logout_without_a_valid_session_stores_nothing",
                         "test_the_login_never_hands_out_a_revoked_value",
                         "test_a_session_db_that_cannot_be_read_fails_closed")]
    for name in tests:
        start = next(i for i, line in enumerate(REVOCATION_TESTS.splitlines(), 1) if line.startswith(f"def {name}("))
        assert any(line.startswith(f"L{start}-") and f"def {name}(" in line for line in out.splitlines()), name
    assert REVOCATION_TESTS.count("\ndef test_") == sum("def test_" in line for line in out.splitlines())
    assert "assert " not in out                                  # no body: the outline only
    assert len(out) < len(REVOCATION_TESTS) / 4


def test_classes_show_their_methods_and_the_ranges_read_the_code(ws, tmp_path):
    out = read(ws, tmp_path, "ledger/api.py")
    assert "class _FailedLogins" in out and "  def record_failure(" in out and "def create_app(" in out
    entry = next(line for line in out.splitlines() if "def create_app(" in line)
    assert entry.startswith("L") and "-" in entry.split(" ", 1)[0], entry
    first, last = (int(x) for x in entry[1:].split(" ", 1)[0].split("-"))
    part = read(ws, tmp_path, "ledger/api.py", start_line=first, end_line=first + 2)
    assert part.startswith(f"[ledger/api.py: lines {first}-{first + 2} of ") and "def create_app(" in part
    assert last >= first


def test_a_small_file_is_still_returned_whole(ws, tmp_path):
    assert read(ws, tmp_path, "ledger/small.py") == "def f():\n    return 1\n"


@pytest.mark.parametrize("path", ["README.md", "ledger/broken.py", "ledger/flat.py"])
def test_other_large_files_show_their_first_part_bounded_by_the_whole_read_limit(ws, tmp_path, path):
    out = read(ws, tmp_path, path)
    assert out.startswith(f"[{path}: lines 1-") and "read another range" in out.splitlines()[0]
    assert len(out) <= getattr(ct, "READ_WHOLE_MAX", 0) + 200


def test_a_range_of_a_large_file_is_unchanged(ws, tmp_path):
    out = read(ws, tmp_path, "README.md", start_line=700, end_line=701)
    assert out == "[README.md: lines 700-701 of 800; read another range with start_line/end_line]\n" \
                  "Line 700 of the readme, with some words in it.\nLine 701 of the readme, with some words in it.\n"


def test_readfile_is_version_3_in_the_agents_and_the_drafters_memo_keys():
    for path in ("codetask/run.py", "codetask/drafter.py"):
        text = (Path(__file__).resolve().parent.parent / path).read_text(encoding="utf-8")
        assert '"ReadFile": "3"' in text and '"ReadFile": "2"' not in text, path


def test_the_tool_schema_and_prompt_are_unchanged_so_old_runs_still_audit():
    assert ct.ReadFile.__doc__.startswith("Read one text file of the workspace, whole or a range of its lines.")
    assert "read one file, whole or a range of lines (start_line, end_line; at most 400 lines)" in \
        ag.system_prompt(ct.TOOLS)


@pytest.mark.parametrize("kept, words", [(True, "start with RunValidation"), (False, "starts again from the original")])
def test_an_attempt_that_wrote_and_ran_out_of_context_is_told_to_read_ranges(kept, words):
    hint = ag._context_hint({"end": "context_limit", "wrote": True, "steps": 14}, CONTRACT["scope"], kept=kept)
    text = " ".join(hint)
    assert "ran out of context after changing files" in text and words in text
    assert "line ranges" in text


def test_an_attempt_that_did_not_write_keeps_its_hint_and_learns_about_outlines():
    hint = " ".join(ag._context_hint({"end": "context_limit", "wrote": False, "read": ["a.py"]}, CONTRACT["scope"],
                                     kept=True))
    assert hint.startswith("It ran out of context before changing any file. Files it read: a.py.")
    assert "line ranges" in hint
