"""SPEC_REPRO_DOCTEST: a python block written as an interactive session (`>>>`) is read with doctest and its examples are run; display only.
The generated program is executed for real here (python -I in a temporary folder), not only read."""
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from acceptance import repro as rp  # noqa: E402
from test_repro import Box, issue  # noqa: E402


def execute(code, tmp_path):
    """(exit code, stdout, stderr) of the program R1 would hand to the sandbox for this block, run here."""
    why = rp.skip_reason(code)
    assert why is None, why
    r = subprocess.run([sys.executable, "-I", "-c", rp.program(code)], cwd=tmp_path, capture_output=True, text=True, timeout=20)
    return r.returncode, r.stdout, r.stderr


# ---- the examples run, like an interactive session ---------------------------------------------------------------------

def test_an_expression_prints_its_repr_and_print_prints(tmp_path):
    rc, out, _ = execute(">>> x = [1, 2]\n>>> x\n[1, 2]\n>>> print('a')\na\n", tmp_path)
    assert (rc, out) == (0, "[1, 2]\na\n")


def test_the_expected_output_is_neither_run_nor_compared(tmp_path):
    rc, out, _ = execute(">>> 1 + 1\n['a', 'b']          # expected something else\n>>> 'z'\nboom(\n", tmp_path)
    assert (rc, out) == (0, "2\n'z'\n")


def test_state_carries_from_one_example_to_the_next(tmp_path):
    rc, out, _ = execute(">>> a = 5\n>>> def f(n):\n...     return n * a\n...\n>>> f(2)\n10\n", tmp_path)
    assert (rc, out) == (0, "10\n")


def test_a_multi_line_example_runs(tmp_path):
    rc, out, _ = execute(">>> for i in range(2):\n...     print(i)\n0\n1\n", tmp_path)
    assert (rc, out) == (0, "0\n1\n")


def test_an_exception_stops_the_block_and_exits_1(tmp_path):
    rc, out, err = execute(">>> print('before')\n>>> 1 / 0\n>>> print('after')\n", tmp_path)
    assert rc == 1 and out == "before\n" and "ZeroDivisionError" in err


def test_source_with_quotes_backslashes_and_unicode_runs_as_written(tmp_path):
    code = ">>> s = '''a'b\"c\\\\d é'''\n>>> print(s)\na'b\"c\\d é\n>>> print(\"x\\ty\")\nx\ty\n"
    rc, out, _ = execute(code, tmp_path)
    assert (rc, out) == (0, "a'b\"c\\d é\nx\ty\n")


# ---- doctest options and what the parser refuses ------------------------------------------------------------------------

def test_an_example_marked_skip_is_not_run(tmp_path):
    rc, out, _ = execute(">>> print('a')\na\n>>> print('b')  # doctest: +SKIP\nb\n>>> print('c')\nc\n", tmp_path)
    assert (rc, out) == (0, "a\nc\n")


def test_a_block_whose_examples_are_all_skipped_is_skipped():
    assert "no runnable doctest example" in rp.skip_reason(">>> print(1)  # doctest: +SKIP\n1\n")


def test_a_block_the_parser_refuses_is_skipped():
    assert "do not parse" in rp.skip_reason(">>> x = 1\n...y = 2\n")


# ---- what did not change ------------------------------------------------------------------------------------------------

def test_a_block_without_a_prompt_gives_the_same_program_as_before():
    code = "import os\nprint(os.name)\n"
    assert rp.program(code) == rp.PRELUDE + code


@pytest.mark.parametrize("code, word", [("x = 1\n...\ny = 2", "bare"), ("$ pip install x\nimport x", "shell"), ("   \n", "empty")])
def test_the_old_skip_rules_for_scripts_stay(code, word):
    assert word in rp.skip_reason(code)


def test_a_dollar_line_still_skips_a_session_block():
    assert "shell" in rp.skip_reason(">>> import x\n$ pip install x\n")


def test_a_bare_dots_line_in_a_session_block_is_not_a_reason_to_skip(tmp_path):
    rc, out, _ = execute(">>> for i in range(1):\n...     print(i)\n...\n0\n", tmp_path)
    assert (rc, out) == (0, "0\n")


# ---- through run(): the stand-in sandbox ------------------------------------------------------------------------------------

def test_run_hands_a_session_block_to_the_sandbox_and_reports_its_status(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    box = Box({"exit_code": 0, "stdout": "2\n", "stderr": ""}, {"exit_code": 1, "stdout": "", "stderr": "ValueError: x\n"})
    res = rp.run(base, issue(">>> 1 + 1\n2", ">>> int('x')\n"), {}, runner=box)
    assert [(r["index"], r["status"]) for r in res] == [(0, "ok"), (1, "raised")]
    assert len(box.calls) == 2 and "doctest" in box.calls[0]["code"] and box.calls[0]["code"].startswith(rp.PRELUDE)


def test_run_still_skips_a_session_block_over_the_size_limit(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    big = ">>> x = '" + "a" * rp.MAX_CODE_BYTES + "'\n"
    box = Box()
    res = rp.run(base, issue(big), {}, runner=box)
    assert res[0]["status"] == "skipped" and "longer than" in res[0]["reason"] and box.calls == []


def test_run_does_not_let_a_parser_refusal_reach_the_job(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    res = rp.run(base, issue(">>> x = 1\n...y = 2\n"), {}, runner=Box())
    assert res[0]["status"] == "skipped" and "do not parse" in res[0]["reason"]


# ---- the real blocks of batch 2 ------------------------------------------------------------------------------------------

BUCKET = (">>> from more_itertools import bucket\n>>> s = bucket(['a1', 'b1', 'a2'], key=lambda x: x[0])\n>>> 'c' in s\nFalse\n>>> sorted(s)\n"
          "['a', 'b', 'c']          # expected ['a', 'b']\n>>> list(s['c'])\n[]\n")
HUMAN_LIST = (">>> human_list(['spam'])\n'spam'\n>>> human_list(['egg', 'bacon', 'spam'], conjunction='or')\n'egg, bacon, or spam'\n")


def test_the_real_issue_blocks_have_runnable_examples():
    assert rp.skip_reason(BUCKET) is None and rp.skip_reason(HUMAN_LIST) is None
    prog = rp.program(BUCKET)
    assert prog.count("compile(") == 5 and "expected ['a', 'b']" not in prog


def test_the_bucket_block_runs_against_a_stand_in_module(tmp_path):
    (tmp_path / "more_itertools.py").write_text("class bucket:\n    def __init__(self, it, key): self.d = {}\n"
                                                "    def __contains__(self, k): return False\n    def __iter__(self): return iter(['a', 'b', 'c'])\n"
                                                "    def __getitem__(self, k): return iter([])\n")
    prog = rp.program(BUCKET).replace("sys.path.insert(0, '/workspace')", f"sys.path.insert(0, {str(tmp_path)!r})")
    r = subprocess.run([sys.executable, "-I", "-c", prog], capture_output=True, text=True, timeout=20)
    assert (r.returncode, r.stdout) == (0, "False\n['a', 'b', 'c']\n[]\n")


# ---- display and label treat it like a script's result --------------------------------------------------------------------

def test_label_and_line_treat_a_session_result_like_a_script_result():
    base = [{"index": 0, "status": "raised", "stdout": "", "stderr_last_line": "KeyError: 'c'", "reason": "", "exit_code": 1}]
    patched = [{"index": 0, "status": "ok", "stdout": "[]\n", "stderr_last_line": "", "reason": "", "exit_code": 0}]
    assert rp.label(base, patched) == ["changed"] and rp.label(base, base) == ["unchanged"]


# ---- a prompt with nothing after it (found by review: CRLF issue bodies, form feed) ---------------------------------------------

@pytest.mark.parametrize("code", ["   >>> \r\n", "   >>> \n", ">>>\n", "  >>> \x0c\n"])
def test_a_bare_prompt_is_not_an_example(code):
    assert "no runnable doctest example" in rp.skip_reason(code)


def test_a_bare_prompt_does_not_stop_the_examples_after_it(tmp_path):
    rc, out, _ = execute("  >>> \x0c\n>>> print(3)\n3\n", tmp_path)
    assert (rc, out) == (0, "3\n")
    rc, out, _ = execute(">>> print(1)\r\n1\r\n>>> \r\n>>> print(2)\r\n2\r\n", tmp_path)
    assert (rc, out) == (0, "1\n2\n")
