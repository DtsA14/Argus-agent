"""SPEC_RED_CAUGHT: the swallowed-traceback gate judges the exceptions the red check saw the test's own code catch
(`caught`), so a test that expects an exception, or that meets a TypeError at its own call site, is not refused for a
name in its message; a record without `caught` (older, vitest, Python < 3.12) keeps the old rule."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_draft import scfg  # noqa: E402,F401  (the fixture)
from test_red_per_node import NODE_A, NODE_B, SCOPE, rec, swallowed  # noqa: E402

from acceptance import validation as va  # noqa: E402
from codetask import drafter as dt  # noqa: E402

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="the path jail and flock need posix; the VM runs these")

VALUE = ["ValueError", "Exception", "BaseException"]


def entry(names=VALUE, handler="tests/test_a.py", paths=("src/lib.py",)):
    return {"names": list(names), "handler": handler, "paths": list(paths)}


def judged(caught, named=("ValueError",), message="f() raised ValueError", **over):
    return swallowed({NODE_A: rec(message, names=list(named), caught=caught, **over)})


# ---- the gate, from the record ---------------------------------------------------------------------------------------

def test_an_exception_of_the_repository_kept_by_the_test_is_refused_and_named_with_its_file():
    out = judged([entry()])
    assert len(out) == 1 and NODE_A in out[0] and "reports ValueError" in out[0]
    assert "ValueError" in out[0] and "src/lib.py" in out[0].split("reports ValueError", 1)[1]


def test_a_test_that_expects_an_exception_nothing_raised_is_not_refused():
    assert judged([], message="f() must raise ValueError") == []


def test_a_type_error_at_the_call_site_has_no_repository_frame_to_lose():
    assert judged([entry(["TypeError", "Exception", "BaseException"], paths=())], ["TypeError"]) == []


def test_an_exception_raised_and_caught_inside_the_repository_is_not_the_tests():
    assert judged([entry(handler="src/lib.py", paths=("src/helper.py",))]) == []


@pytest.mark.parametrize("paths", [["tests/helpers.py"], ["conftest.py"], ["pkg/thing_test.py"], ["/usr/lib/x.py"]])
def test_a_helper_of_the_tests_is_not_the_repositorys_code(paths):
    assert judged([entry(paths=paths)]) == []


def test_a_base_class_named_in_the_message_matches_the_class_that_was_caught():
    out = judged([entry(["KeyError", "LookupError", "Exception", "BaseException"])], ["LookupError"],
                 "lookup raised LookupError")
    assert len(out) == 1 and "LookupError" in out[0]


def test_another_exception_caught_than_the_one_named_is_not_refused():
    assert judged([entry(["KeyError", "LookupError", "Exception", "BaseException"])]) == []


def test_one_matching_entry_among_others_is_enough():
    assert len(judged([entry(["KeyError"], paths=()), entry()])) == 1


def test_each_node_is_judged_by_its_own_caught():
    out = swallowed({NODE_A: rec("f() raised ValueError", names=["ValueError"], caught=[entry()]),
                     NODE_B: rec("f() raised ValueError", names=["ValueError"], caught=[])})
    assert len(out) == 1 and NODE_A in out[0] and NODE_B not in out[0]


def test_a_traceback_that_reaches_the_repository_is_still_not_refused():
    assert judged([entry()], paths=["tests/test_a.py", "src/lib.py"]) == []


@pytest.mark.parametrize("caught", [None, "missing"])
def test_without_caught_the_old_rule_applies(caught):
    r = rec("f() must raise ValueError", names=["ValueError"])
    if caught is None:
        r["caught"] = None
    assert len(swallowed({NODE_A: r})) == 1 and "caught" not in str(swallowed({NODE_A: r}))


@pytest.mark.parametrize("bad", ["ValueError", {"names": ["ValueError"]}, [1], ["x"], [{"names": "ValueError",
                         "handler": "tests/test_a.py", "paths": []}], [{"names": ["ValueError"], "handler": 1,
                         "paths": []}], [{"names": ["ValueError"], "handler": "tests/test_a.py", "paths": "src/a.py"}],
                         [{"names": [1], "handler": "tests/test_a.py", "paths": []}],
                         [{"names": ["ValueError"], "paths": []}]])
def test_a_caught_that_cannot_be_read_is_refused_not_passed(bad):
    out = judged(bad)
    assert len(out) == 1 and NODE_A in out[0] and "could not be read" in out[0]


def test_a_plain_assert_is_not_refused_whatever_was_caught():
    assert judged([entry()], named=(), message="assert 1 == 0") == []


# ---- the red check in the sandbox ------------------------------------------------------------------------------------

LIB = '''def strict(x):
    if x < 0:
        raise ValueError(f"negative: {x}")
    return x


def lookup(d):
    return d["x"]


def tolerant(x):
    try:
        raise ValueError("internal")
    except ValueError:
        return 0


def plain(x, y=1):
    return x + y


def boom(cls):
    raise cls("x")
'''
CASES = '''import pytest
from src import lib


def test_swallow():
    err = None
    try:
        lib.strict(-1)
    except ValueError as e:
        err = e
    pytest.fail(f"strict failed with ValueError: {err}")


def test_expects():
    lib.tolerant(1)
    pytest.fail("tolerant must raise ValueError")


def test_call_site():
    err = None
    try:
        lib.plain(1, z=2)
    except TypeError as e:
        err = e
    pytest.fail(f"plain raised TypeError: {err}")


def test_base_name():
    err = None
    try:
        lib.lookup({})
    except LookupError as e:
        err = e
    pytest.fail(f"lookup raised LookupError {err!r}")


def test_inside_repo():
    lib.tolerant(1)
    pytest.fail("tolerant must raise ValueError")


def test_in_except_block():
    try:
        lib.strict(-1)
    except ValueError as e:
        pytest.fail(f"strict raised ValueError {e}")


def helper_catches(x):
    try:
        return lib.strict(x)
    except ValueError:
        return None


def test_helper_catches_then_fails():
    helper_catches(-1)
    assert False, "ValueError expected"


def test_passes_after_catching():
    try:
        lib.strict(-1)
    except ValueError:
        pass
'''
NODES = [f"tests/test_cases.py::{n}" for n in ("test_swallow", "test_expects", "test_call_site", "test_base_name",
                                                 "test_inside_repo", "test_in_except_block",
                                                 "test_helper_catches_then_fails", "test_passes_after_catching")]


def repo(tmp_path, tests=CASES):
    tmp_path.chmod(0o755)                                     # read by the sandbox's own user
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "__init__.py").write_text("")
    (tmp_path / "conftest.py").write_text("")
    (tmp_path / "src" / "lib.py").write_text(LIB)
    (tmp_path / "tests" / "test_cases.py").write_text(tests)
    return tmp_path


def test_the_red_check_records_what_the_tests_caught(tmp_path, scfg):
    got, why = va.red_check(NODES, str(repo(tmp_path)), scfg, timeout_s=120, environment="argus")
    assert why is None, why
    sw, ex, cs, bn, ir, ib, hc, ps = (got[n] for n in NODES)
    assert sw["caught"] == [{"names": ["ValueError", "Exception", "BaseException"], "handler": "tests/test_cases.py",
                             "paths": ["src/lib.py"]}]
    assert ex["caught"] == [] and ir["caught"] == []        # nothing reached the test (tolerant handles its own)
    assert cs["caught"] == []                               # raised at the call site: no frame deeper than the test's
    assert bn["caught"][0]["names"] == ["KeyError", "LookupError", "Exception", "BaseException"]
    assert bn["caught"][0]["paths"] == ["src/lib.py"]
    assert ib["caught"][0]["paths"] == ["src/lib.py"]       # caught inside the except block: kept for the record
    assert hc["caught"][0]["handler"] == "tests/test_cases.py" and hc["caught"][0]["paths"] == ["src/lib.py"]
    assert ps["outcome"] == "passed" and ps.get("caught") is None      # a test that passes keeps its short record
    assert all(r["assertion"] for r in (sw, ex, cs, bn, ir, ib, hc))


def test_the_gate_on_the_real_record_refuses_only_what_was_swallowed(tmp_path, scfg):
    got, why = va.red_check(NODES, str(repo(tmp_path)), scfg, timeout_s=120, environment="argus")
    assert why is None, why
    draft = {"contract": {"scope": SCOPE}}
    refused = {n for n in NODES if dt.swallowed_problems(draft, {"baseline": {"t": {"red_check": {n: got[n]}}}})}
    # test_in_except_block keeps the traceback through the context chain: its repo_paths hold src/lib.py
    assert refused == {NODES[0], NODES[3], NODES[6]}


def test_a_tool_id_that_cannot_be_taken_falls_back_to_the_old_rule(tmp_path, scfg, monkeypatch):
    patched = va.RED_CHECK.replace("mon.use_tool_id(TOOL,", "mon.use_tool_id(99,")      # not a tool id: use_tool_id refuses
    assert patched != va.RED_CHECK
    monkeypatch.setattr(va, "RED_CHECK", patched)
    got, why = va.red_check(NODES[:2], str(repo(tmp_path)), scfg, timeout_s=120, environment="argus")
    assert why is None, why
    assert got[NODES[0]]["caught"] is None and got[NODES[1]]["caught"] is None
    draft = {"contract": {"scope": SCOPE}}
    assert dt.swallowed_problems(draft, {"baseline": {"t": {"red_check": {NODES[1]: got[NODES[1]]}}}})   # as before


def test_many_caught_exceptions_fall_back_to_the_old_rule_not_a_cut_list(tmp_path, scfg):
    tests = ("import pytest\nfrom src import lib\n\n\ndef test_many():\n    for i in range(25):\n        try:\n"
             "            lib.boom(type(f'E{i}Error', (Exception,), {}))\n        except Exception:\n            pass\n"
             "    pytest.fail('ValueError')\n")
    node = "tests/test_cases.py::test_many"
    got, why = va.red_check([node], str(repo(tmp_path, tests=tests)), scfg, timeout_s=120, environment="argus")
    assert why is None, why
    assert got[node]["caught"] is None


def test_a_catch_the_callback_cannot_read_makes_the_test_unwatched_not_clean(tmp_path, scfg):
    tests = ("import pytest\nfrom src import lib\n\n\nclass Meta(type):\n    @property\n    def __name__(cls):\n"
             "        raise RuntimeError('no name')\n\n\nclass Odd(Exception, metaclass=Meta):\n    pass\n\n\n"
             "def test_odd():\n    err = None\n    try:\n        lib.boom(Odd)\n    except Exception as e:\n"
             "        err = e\n    pytest.fail(f'ValueError {err!r}')\n")
    node = "tests/test_cases.py::test_odd"
    got, why = va.red_check([node], str(repo(tmp_path, tests=tests)), scfg, timeout_s=120, environment="argus")
    assert why is None, why
    assert got[node]["assertion"] and got[node]["caught"] is None


def test_the_monitoring_does_not_change_a_test_outcome(tmp_path, scfg):
    got, why = va.red_check(NODES, str(repo(tmp_path)), scfg, timeout_s=120, environment="argus")
    assert why is None, why
    assert [got[n]["outcome"] for n in NODES] == ["failed"] * 7 + ["passed"]


def test_the_limits_name_the_caught_list():
    assert va.RED_LIMITS["caught"] == 20
