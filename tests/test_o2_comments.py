"""O2 narrowing (docs/reviews/SPEC_O2_COMMENTS.md): in a Python file, text that cannot run (a comment, a docstring or any standalone
string statement) does not trigger the forger patterns; code is scanned as before. Anything that makes the file's lines uncertain
(a syntax error, a bare carriage return) keeps the old, wider scan. Everything goes through `check`, the gate's public entry."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_test_detection import scan  # noqa: E402


def hits(tmp_path, text, ext="py"):
    c = scan(tmp_path, {f"src/m.{ext}": text})
    return [(e["line"], e["pattern"]) for e in (c.get("evidence") or {}).get("hits", [])]


def names(tmp_path, text, ext="py"):
    return {p for _, p in hits(tmp_path, text, ext)}


# ---- text that cannot run is not a hit -------------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    '"""Never call os._exit(0) here."""\nx = 1\n',                                         # module docstring
    'def f():\n    """Do not os._exit(0); see /proc/self/status."""\n    return 1\n',        # function docstring
    'class C:\n    """os.abort() is not used."""\n',                                        # class docstring
    "x = 1  # see /proc/self/status\n",                                                    # trailing comment
    "x = 1  # os._exit(0) would end the run\n",
    'def f():\n    x = 1\n    """os.execv is not used here"""\n    return x\n',             # a standalone string statement
    "x = 1  # S_ISFIFO and os.write(1, b'x')\n",
])
def test_text_that_cannot_run_does_not_trigger_the_forger_patterns(tmp_path, text):
    assert hits(tmp_path, text) == []


# ---- code is still a hit ----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("text, pattern", [
    ("import os\nos._exit(0)  # fine\n", "os._exit"),                                      # code before a comment
    ('x = "#"; import os; os._exit(0)\n', "os._exit"),                                     # a # inside a string hides nothing
    ('import os\nf"{os._exit(0)}"\n', "os._exit"),                                         # an f-string runs its expressions
    ('exec("import os; os._exit(0)")\n', "os._exit"),                                      # a string given to exec is not a statement
    ('def f():\n    """doc"""\n    import os\n    os.abort()\n', "abrupt exit"),            # code after a docstring
    ("é = 'é'; import os; os._exit(0)\n", "os._exit"),                                    # non-ASCII before the call (byte offsets)
])
def test_code_is_still_a_hit(tmp_path, text, pattern):
    assert pattern in names(tmp_path, text)


def test_a_non_ascii_comment_is_cut_at_the_right_column(tmp_path):
    assert hits(tmp_path, "é = 1  # os._exit(0)\n") == []
    assert "os._exit" in names(tmp_path / "b", "é = 1; import os; os._exit(0)  # é\n")


def test_the_line_numbers_do_not_move(tmp_path):
    assert hits(tmp_path, '"""doc\nos._exit(0)\nmore"""\nimport os\nos._exit(0)\n') == [(5, "os._exit")]


# ---- when the lines are uncertain, the old scan stays --------------------------------------------------------------------

def test_a_file_that_does_not_parse_keeps_the_old_scan(tmp_path):
    assert hits(tmp_path, "def (:\n    x = 1  # os._exit(0)\n") == [(2, "os._exit")]


def test_a_bare_carriage_return_keeps_the_old_scan(tmp_path):
    assert hits(tmp_path, "x = 1  # os._exit(0)\r y = 2\r") == [(1, "os._exit")]


# ---- what was not narrowed ----------------------------------------------------------------------------------------------

def test_javascript_is_not_narrowed(tmp_path):
    assert names(tmp_path, "x = 1 // process.exit(0)\n", "js") == {"process.exit"}
    assert names(tmp_path / "b", "process.exit(0) // done\n", "js") == {"process.exit"}


def test_the_detection_patterns_are_not_narrowed(tmp_path):
    assert "PYTEST_CURRENT_TEST" in names(tmp_path, '"""uses PYTEST_CURRENT_TEST"""\n')
    assert "sys.argv+pytest" in names(tmp_path / "b", "import sys\nx = sys.argv  # pytest\n")


def test_a_change_whose_only_mention_is_a_docstring_passes_and_real_code_fails(tmp_path):
    assert scan(tmp_path, {"src/app.py": '"""Never call os._exit here."""\nVALUE = 1\n'})["status"] == "pass"
    assert scan(tmp_path / "b", {"src/app.py": '"""doc"""\nimport os\nos._exit(0)\n'})["status"] == "fail"
