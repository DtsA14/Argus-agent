"""ReadFile line ranges and ListFiles bounds (fast lane, after SWE v0 batch 4): sympy-24562's agent could not read
sympy/core/numbers.py (136,480 bytes, over MAX_READ) and spent 4 attempts on SearchFiles; its first ListFiles alone was
~25,000 tokens. A large file is read in parts, a listing is capped, and the issue bound is 8,000 characters."""
import sys

import pytest

from acceptance import contract as ac
from codetask import agent as ag
from codetask import tools as ct
from harness.events import EventLog

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="the path jail needs openat; the VM runs these")

CONTRACT = {"contract": "t", "inputs": {"issue": "x"}, "scope": {"writable": ["src/**"], "protected": ["tests/**"]},
            "validation": [], "artifacts": [{"schema": "claims_v2"}]}
ALL = ["list_files", "search_files", "read_file", "write_file", "run_validation"]


def box(ws, tmp_path):
    return ct.Toolbox(str(ws), CONTRACT, {}, ALL, EventLog(tmp_path / "e.jsonl"))


def read(b, path, **kw):
    return b.run({"name": "ReadFile", "args": {"path": path, **kw}})["content"]


@pytest.fixture
def ws(tmp_path):
    w = tmp_path / "ws"
    (w / "src").mkdir(parents=True)
    (w / "src" / "small.py").write_text("a = 1\nb = 2\n")
    (w / "src" / "big.py").write_text("".join(f"line_{n:05d} = {'x' * 300}\n" for n in range(1, 1001)))  # ~320 KB
    return w


def test_a_small_file_without_a_range_is_returned_whole_and_unchanged(ws, tmp_path):
    assert read(box(ws, tmp_path), "src/small.py") == "a = 1\nb = 2\n"


def test_a_file_over_max_read_is_shown_in_part_not_refused(ws, tmp_path):
    out = read(box(ws, tmp_path), "src/big.py")
    assert not out.startswith("Refused")
    assert out.startswith("[src/big.py: lines 1-") and "of 1000; read another range" in out
    assert "line_00001 =" in out and "line_01000 =" not in out
    assert len(out) <= ct.MAX_READ + 200


def test_a_range_returns_exactly_those_lines(ws, tmp_path):
    out = read(box(ws, tmp_path), "src/big.py", start_line=700, end_line=702)
    body = out.split("\n", 1)[1]
    assert out.startswith("[src/big.py: lines 700-702 of 1000;")
    assert [line[:10] for line in body.splitlines()] == ["line_00700", "line_00701", "line_00702"]


def test_a_part_is_bounded_in_lines_and_characters(ws, tmp_path):
    out = read(box(ws, tmp_path), "src/big.py", start_line=1, end_line=1000)
    body = out.split("\n", 1)[1].splitlines()
    assert len(body) <= ct.READ_MAX_LINES and len(out) <= ct.MAX_READ + 200
    assert out.startswith(f"[src/big.py: lines 1-{len(body)} of 1000;")


def test_a_whole_small_file_read_by_range_says_it_is_whole(ws, tmp_path):
    assert read(box(ws, tmp_path), "src/small.py", start_line=1, end_line=5) == "[src/small.py: lines 1-2 of 2]\na = 1\nb = 2\n"


@pytest.mark.parametrize("kw", [{"start_line": -1}, {"start_line": 5, "end_line": 2}, {"end_line": "3"}])
def test_bad_ranges_are_rejected(ws, tmp_path, kw):
    assert read(box(ws, tmp_path), "src/big.py", **kw).startswith("Rejected:")


def test_a_start_past_the_end_says_how_long_the_file_is(ws, tmp_path):
    assert read(box(ws, tmp_path), "src/small.py", start_line=9) == "src/small.py has 2 lines; start_line 9 is past its end."


def test_a_range_still_goes_through_the_path_jail(ws, tmp_path):
    assert read(box(ws, tmp_path), "../outside.py", start_line=1).startswith("Refused")


def test_a_file_over_the_ranged_limit_is_still_refused(ws, tmp_path):
    (ws / "src" / "huge.txt").write_text("y" * (ct.READ_MAX_FILE + 1))
    assert read(box(ws, tmp_path), "src/huge.txt", start_line=1).startswith("Refused")


def test_listfiles_is_capped_and_says_how_many_more(tmp_path):
    w = tmp_path / "ws"
    (w / "pkg").mkdir(parents=True)
    for n in range(ct.LIST_MAX_FILES + 25):
        (w / "pkg" / f"m{n:04d}.py").write_text("")
    out = box(w, tmp_path).run({"name": "ListFiles", "args": {}})["content"].splitlines()
    assert len(out) == ct.LIST_MAX_FILES + 1 and out[-1].startswith("... 25 more files not shown")


def test_listfiles_under_a_directory_lists_only_that_directory(ws, tmp_path):
    (ws / "docs").mkdir()
    (ws / "docs" / "a.md").write_text("")
    b = box(ws, tmp_path)
    assert b.run({"name": "ListFiles", "args": {"path": "src"}})["content"] == "src/big.py\nsrc/small.py"
    assert b.run({"name": "ListFiles", "args": {"path": "nope"}})["content"] == "No files under 'nope'."
    assert b.run({"name": "ListFiles", "args": {"path": "../x"}})["content"].startswith("Refused")


def test_the_prompt_tells_the_agent_about_ranges_and_the_listing_cap():
    p = ag.system_prompt([ct.ListFiles, ct.ReadFile])
    assert "start_line" in p and "at most 300" in p


def test_the_issue_bound_is_8000_characters():
    from codetask import drafter
    assert ac.MAX_ISSUE == drafter.MAX_ISSUE == 8000


def test_router_jobs_give_the_agent_30_steps_and_config_yaml_keeps_12_for_the_evals():
    from runner import load_config
    cfg = load_config()
    assert cfg["code_task"]["max_steps"] == 12 and cfg["router"]["overrides"]["code_task.max_steps"] == 30
