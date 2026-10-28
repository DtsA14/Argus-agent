"""What the agent is told after a write and after a validation without a pytest summary (fast lane, after the argus-ledger
practice stages and the sympy-24562 dev run: the agent replaced numbers.py, 4,487 lines, with a wrapper that raised
ImportError at import; pytest exited 4 with the reason on stderr only, so the agent saw "no pytest summary" twice)."""
import sys

import pytest

from acceptance import validation as va
from codetask.tools import Toolbox
from harness.events import EventLog

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="the path jail needs openat; the VM runs these")

CONTRACT = {"contract": "t", "scope": {"writable": ["src/**"], "protected": ["tests/**"]}, "validation": []}
BIG = "".join(f"def f{n}(x):\n    return x + {n}\n\n" for n in range(100))          # 300 lines


def setup(tmp_path):
    ws = tmp_path / "ws"
    (ws / "src").mkdir(parents=True)
    (ws / "src" / "big.py").write_text(BIG)
    (ws / "src" / "small.py").write_text("a = 1\nb = 2\n")
    box = Toolbox(str(ws), CONTRACT, {}, ("read_file", "write_file", "edit_file"), EventLog(tmp_path / "e.jsonl"),
                  journal=tmp_path / "journal.jsonl")
    return box, ws


def write(box, path, content):
    return box.run({"name": "WriteFile", "args": {"path": path, "content": content}})["content"]


def edit(box, path, old, new):
    return box.run({"name": "EditFile", "args": {"path": path, "old_text": old, "new_text": new}}, step_key="k1")["content"]


# ---- WriteFile that throws most of a large file away --------------------------------------------------------------

def test_replacing_most_of_a_large_file_is_reported_and_the_write_still_happens(tmp_path):
    box, ws = setup(tmp_path)
    out = write(box, "src/big.py", "from original import *\n")
    assert "Warning: src/big.py had 300 lines and now has 1" in out and "EditFile" in out
    assert (ws / "src" / "big.py").read_text() == "from original import *\n"


@pytest.mark.parametrize("path, content", [
    ("src/big.py", "".join(f"def f{n}(x):\n    return x + {n}\n\n" for n in range(75))),   # keeps 3/4 of its lines
    ("src/small.py", ""),                              # a small file
    ("src/new.py", "x = 1\n"),                         # a new file
])
def test_no_shrink_warning_for_a_partial_rewrite_a_small_file_or_a_new_file(tmp_path, path, content):
    box, _ = setup(tmp_path)
    assert "Warning" not in write(box, path, content)


# ---- Python that does not parse ------------------------------------------------------------------------------------

def test_a_write_or_edit_that_leaves_python_unparseable_says_where(tmp_path):
    box, ws = setup(tmp_path)
    out = write(box, "src/small.py", "def f(:\n    pass\n")
    assert "Warning: src/small.py does not parse as Python" in out and "line 1" in out
    out = edit(box, "src/big.py", "def f3(x):\n", "def f3(x)\n")
    assert "Warning: src/big.py does not parse as Python" in out
    assert "def f3(x)\n" in (ws / "src" / "big.py").read_text()                     # the edit happened


def test_parseable_python_and_other_files_get_no_parse_warning(tmp_path):
    box, _ = setup(tmp_path)
    assert "Warning" not in write(box, "src/small.py", "a = 2\n")
    assert "Warning" not in write(box, "src/notes.txt", "def f(:\n")


def test_the_parse_check_never_runs_the_code(tmp_path):
    box, _ = setup(tmp_path)
    marker = tmp_path / "ran"
    out = write(box, "src/small.py", f"open({str(marker)!r}, 'w').write('x')\nraise SystemExit(3)\n")
    assert "Warning" not in out and not marker.exists()


# ---- A pytest run without a summary --------------------------------------------------------------------------------

SPEC = {"id": "target", "executable": "python", "args": ["-m", "pytest", "tests/test_x.py"], "timeout_s": 60,
        "min_tests": 1, "max_skipped": 0, "must_pass": ["tests/test_x.py::test_a"]}
CONFTEST_ERROR = ("ImportError while loading conftest '/workspace/conftest.py'.\n"
                  "sympy/core/numbers.py:151: in <module>\n"
                  "    raise ImportError('could not locate the original sympy/core/numbers.py')\n"
                  "E   ImportError: could not locate the original sympy/core/numbers.py\n")


def run(stdout, stderr, exit_code):
    return {"exit_code": exit_code, "stdout": stdout, "stderr": stderr, "timed_out": False, "killed": False,
            "truncated": False, "output_limit_exceeded": False, "cleanup_failed": False}


def test_without_a_pytest_summary_the_output_shown_includes_stderr():
    v = va.judge_result(SPEC, run("", CONFTEST_ERROR, 4))
    assert v["status"] == "fail"
    assert "--- stderr ---" in v["evidence"]["output_tail"]
    assert "could not locate the original sympy/core/numbers.py" in v["evidence"]["output_tail"]


PYTEST_OK = ("collecting ... collected 1 item\n\n"
             "tests/test_x.py::test_a PASSED\n\n"
             "======== 1 passed in 0.01s ========\n")


def test_with_a_pytest_summary_the_output_shown_is_stdout_only():
    out = PYTEST_OK
    v = va.judge_result(SPEC, run(out, "some warning on stderr\n", 0))
    assert v["status"] == "pass", v["reason"]
    assert v["evidence"]["output_tail"] == out
