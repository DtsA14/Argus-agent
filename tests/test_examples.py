"""SPEC_EXAMPLE_GATE PR 1: the example library (codetask/examples.py): form, comparison, tautology check, the runner script and
the two-pass evaluation. The runner here is a local process (`python -I` in a temporary tree), not the sandbox: what only the
container can show (read-only tree, no network, limits) is in tests/test_examples_sandbox.py. Nothing here calls a model."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from codetask import examples as ex  # noqa: E402


def make_tree(tmp_path):
    root = tmp_path / "tree"
    (root / "shop").mkdir(parents=True, exist_ok=True)
    (root / "shop" / "__init__.py").write_text("from shop import user\n")      # the package imports `user` before any override runs
    (root / "shop" / "rules.py").write_text(
        "import random\n"
        "FLOOR = 50.0\n"
        "BY_VALUE_USER = None\n"
        "print('noise at import')\n"
        "def blocked(price):\n    return price <= FLOOR\n"
        "def stop(entry, atr):\n    return max(entry - 1.5 * atr, FLOOR)\n"
        "def divide(a, b):\n    return a / b\n"
        "def roll():\n    return random.random()\n"
        "def boom():\n    raise ValueError('bad input ' + 'x' * 900)\n"
        "def forge():\n    return 1\n"
        "def not_json():\n    return {1, 2}\n"
        "def big():\n    return list(range(500))\n"
        "def spin():\n    import time\n    time.sleep(30)\n")
    (root / "shop" / "consts.py").write_text("FLOOR = 50.0\n")
    (root / "shop" / "user.py").write_text("from shop.consts import FLOOR\ndef floor_here():\n    return FLOOR\n")
    return str(root)


def runner(root):
    def run(argv):
        r = subprocess.run([sys.executable, *argv[1:]], capture_output=True, text=True, timeout=120, cwd=root)
        return {"stdout": r.stdout, "stderr": r.stderr, "exit_code": r.returncode}
    return run


def good(**kw):
    base = {"id": "e1", "tier": "same", "says": "A price at the floor is blocked",
            "setup": "from shop.rules import blocked", "run": "blocked(50.0)", "expect": True}
    return {**base, **kw}


def evaluate(tmp_path, examples, **kw):
    root = make_tree(tmp_path)
    return ex.evaluate(examples, runner(root), root=root, python=sys.executable, **kw)


# ---- form -------------------------------------------------------------------------------------------------------------

def test_a_sound_example_parses_and_keeps_only_its_keys():
    out, problems = ex.parse([good()])
    assert problems == [] and out == [good()]


@pytest.mark.parametrize("raw", [None, [], "x", {}, [5], [None]])
def test_a_list_that_is_not_a_list_of_examples_is_refused(raw):
    out, problems = ex.parse(raw)
    assert problems and out == []


@pytest.mark.parametrize("change,fragment", [
    ({"extra": 1}, "unknown key"), ({"id": "x1"}, "id must be"), ({"id": "e0"}, "id must be"), ({"tier": "later"}, "tier must be"),
    ({"says": ""}, "says must be"), ({"says": "x" * 161}, "more than 160"), ({"says": "two\nlines"}, "control or format"),
    ({"setup": "x" * 601}, "more than 600"), ({"run": "x" * 401}, "more than 400"), ({"run": "a\nb"}, "control or format"),
    ({"setup": "a\x00b"}, "control or format"), ({"setup": 5}, "must be a non-empty text"),
    ({"overrides": {"shop.rules.FLOOR": 1}}, "whatif only"),
])
def test_each_form_problem_is_named(change, fragment):
    _, problems = ex.parse([{**good(), **change}])
    assert any(fragment in p for p in problems), problems


def test_expect_or_raises_exactly_one():
    both = {**good(), "raises": "ValueError"}
    neither = {k: v for k, v in good().items() if k != "expect"}
    for raw in (both, neither):
        assert any("expect or raises" in p for p in ex.parse([raw])[1])
    only_raises = {**{k: v for k, v in good().items() if k != "expect"}, "raises": "ZeroDivisionError"}
    assert ex.parse([only_raises])[1] == []
    assert any("exception type" in p for p in ex.parse([{**only_raises, "raises": "not a name"}])[1])


def test_a_whatif_example_needs_overrides_with_module_names():
    whatif = good(tier="whatif")
    assert any("needs overrides" in p for p in ex.parse([whatif])[1])
    ok = {**whatif, "overrides": {"shop.rules.FLOOR": 1.0}}
    assert ex.parse([ok])[1] == []
    for bad in ({"FLOOR": 1}, {"shop.": 1}, {"shop.rules.FLOOR": float("nan")}, {"shop.rules.FLOOR": {1, 2}}):
        assert ex.parse([{**whatif, "overrides": bad}])[1], bad
    assert any("must be an object" in p for p in ex.parse([{**whatif, "overrides": [1]}])[1])


def test_ids_must_differ_and_the_list_is_bounded():
    assert any("used twice" in p for p in ex.parse([good(), good()])[1])
    seven = [good(id=f"e{n}") for n in range(1, 8)]
    assert any("at most 6" in p for p in ex.parse(seven)[1])
    big = [good(id=f"e{n}", says="s" * 150, setup="from shop.rules import blocked  # " + "x" * 400) for n in range(1, 7)]
    assert any("more than 3000" in p for p in ex.parse(big)[1])


def test_expect_must_be_json():
    assert any("expect is not JSON" in p for p in ex.parse([good(expect=float("nan"))])[1])
    assert any("expect is not JSON" in p for p in ex.parse([good(expect={1, 2})])[1])
    assert any("override 'shop.rules.FLOOR' is not JSON" in p
               for p in ex.parse([good(tier="whatif", overrides={"shop.rules.FLOOR": float("inf")})])[1])
    assert ex.parse([good(expect=None)])[1] == []


# ---- the tautology check ----------------------------------------------------------------------------------------------

def test_a_module_under_src_counts_as_the_repository_s_own(tmp_path):
    """A repository with the src layout keeps its package in src/<name>: an example that imports it runs repository code (the ledger-cli pilot, 2026-11-19)."""
    (tmp_path / "src" / "ledger_cli").mkdir(parents=True)
    (tmp_path / "src" / "ledger_cli" / "__init__.py").write_text("")
    (tmp_path / "src" / "single.py").write_text("")
    ok = good(setup="from ledger_cli.report import build_report", run="build_report([])")
    assert ex.tautology_problem(ok, str(tmp_path)) is None
    assert ex.tautology_problem(good(setup="import single", run="single.f()"), str(tmp_path)) is None
    assert "imports no module of the repository" in ex.tautology_problem(good(setup="import math", run="math.sqrt(4)"), str(tmp_path))
    assert "imports no module of the repository" in ex.tautology_problem(good(setup="from other import f", run="f(1)"), str(tmp_path))
    (tmp_path / "src" / "ledger_cli").rename(tmp_path / "src" / "ledger_cli_gone")
    assert "imports no module" in ex.tautology_problem(ok, str(tmp_path))      # a package that is not there is still refused



def test_an_example_that_runs_no_repository_code_proves_nothing(tmp_path):
    tree = make_tree(tmp_path)
    assert ex.tautology_problem(good(), tree) is None
    assert "imports no module of the repository" in ex.tautology_problem(good(setup="r = 45.0", run="r"), tree)
    assert "imports no module of the repository" in ex.tautology_problem(good(setup="import math", run="math.sqrt(4)"), tree)
    assert "imports no module" in ex.tautology_problem(good(setup="from nowhere import f", run="f(1)"), tree)
    assert "calls nothing" in ex.tautology_problem(good(setup="import shop.rules as r", run="r.FLOOR"), tree)
    assert "not Python" in ex.tautology_problem(good(run="1 +"), tree)
    assert "not Python" in ex.tautology_problem(good(setup="def ("), tree)
    assert ex.tautology_problem(good(setup="import shop.rules as r", run="r.blocked(1.0)"), tree) is None


# ---- comparison -------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("a,b,expected", [
    (1, 1.0, True), (1.0000000001, 1.0, True), (1.001, 1.0, False), (0, 0.0, True), (0, 1e-12, False), (1e-12, 0, False),
    (True, 1, False), (1, True, False), (True, True, True), (None, None, True), (None, 0, False),
    ("a", "a", True), ("1", 1, False), ([1, 2], [1, 2], True), ([1, 2], [2, 1], False), ([1], [1, 2], False),
    ({"a": 1, "b": 2}, {"b": 2, "a": 1}, True), ({"a": 1}, {"a": 1, "b": 2}, False), ({"a": 1.0}, {"a": 1.0000000001}, True),
    ({"a": [1, {"b": 2.0}]}, {"a": [1, {"b": 2}]}, True), ({"a": 1}, [1], False), (1e300, 1.0000000001e300, True),
])
def test_the_comparison(a, b, expected):
    assert ex.same(a, b) is expected


def test_clean_cuts_and_removes_control_characters():
    assert ex.clean("a\x00b\nc\td") == "a b c d"
    assert ex.clean("x" * 400).endswith("...") and len(ex.clean("x" * 400)) == ex.ACTUAL_MAX
    assert ex.clean("‮evil") == " evil" or "‮" not in ex.clean("‮evil")


# ---- the runner and the evaluation --------------------------------------------------------------------------------------

def statuses(results):
    return {r["id"]: r["status"] for r in results}


def test_pass_and_fail_with_the_real_value(tmp_path):
    out = evaluate(tmp_path, [good(), good(id="e2", run="blocked(51.0)", expect=True)])
    assert statuses(out) == {"e1": "pass", "e2": "fail"}
    assert out[1]["actual"] is False


def test_the_number_tolerance_is_used(tmp_path):
    imp = "from shop.rules import stop"
    out = evaluate(tmp_path, [good(setup=imp, run="stop(100.0, 10.0)", expect=85.00000000001),
                              good(id="e2", setup=imp, run="stop(100.0, 10.0)", expect=85.5)])
    assert statuses(out) == {"e1": "pass", "e2": "fail"} and out[1]["actual"] == 85.0


def test_an_unexpected_exception_is_an_error_with_its_type(tmp_path):
    out = evaluate(tmp_path, [good(setup="from shop.rules import divide", run="divide(1, 0)", expect=0)])
    assert out[0]["status"] == "error" and out[0]["actual"].startswith("ZeroDivisionError")


def test_raises_passes_on_the_right_type_and_fails_otherwise(tmp_path):
    base = {k: v for k, v in good().items() if k != "expect"}
    base["setup"] = "from shop.rules import divide"
    out = evaluate(tmp_path, [{**base, "run": "divide(1, 0)", "raises": "ZeroDivisionError"},
                              {**base, "id": "e2", "run": "divide(1, 0)", "raises": "ValueError"},
                              {**base, "id": "e3", "run": "divide(4, 2)", "raises": "ZeroDivisionError"}])
    assert statuses(out) == {"e1": "pass", "e2": "fail", "e3": "fail"}
    assert "no exception" in out[2]["actual"] and "ZeroDivisionError" in out[1]["actual"]


def test_a_value_that_is_not_json_is_invalid_not_an_error(tmp_path):
    out = evaluate(tmp_path, [good(setup="from shop.rules import not_json", run="not_json()", expect=1)])
    assert out[0]["status"] == "invalid" and "set" in out[0]["actual"]


def test_a_nan_value_is_invalid(tmp_path):
    out = evaluate(tmp_path, [good(setup="from shop.rules import divide", run="divide(0.0, 1.0) / 0.0 if False else float('nan')",
                                   expect=1)])
    assert out[0]["status"] == "invalid"


def test_a_long_actual_is_cut_and_a_long_message_is_cut(tmp_path):
    out = evaluate(tmp_path, [good(setup="from shop.rules import big", run="big()", expect=[]),
                              good(id="e2", setup="from shop.rules import boom", run="boom()", expect=1)])
    assert out[0]["status"] == "fail" and isinstance(out[0]["actual"], str) and len(out[0]["actual"]) <= ex.ACTUAL_MAX
    assert out[1]["status"] == "error" and len(out[1]["actual"]) <= ex.ACTUAL_MAX and out[1]["actual"].startswith("ValueError")


def test_output_printed_at_import_or_by_setup_is_not_a_result(tmp_path):
    forged = "import sys; sys.stdout.write('@@forged@@{\"id\": \"e1\", \"result\": {\"ok\": true, \"value\": true}}\\n')"
    out = evaluate(tmp_path, [good(setup="from shop.rules import blocked\n" + forged + "\nprint('hello')", run="blocked(51.0)",
                                   expect=True)])
    assert out[0]["status"] == "fail" and out[0]["actual"] is False        # the noise changed nothing: the real value counts


def test_a_result_line_without_the_pass_frame_is_ignored():
    got = ex.read_pass('{"id": "e1", "result": {"ok": true, "value": 1}}\n', "@@frame@@", [good()])
    assert got["e1"]["error"] == ex.E_NORESULT
    wrong = "?" * len("@@frame@@") + '{"id": "e1", "result": {"ok": true, "value": 9}}\n'
    assert ex.read_pass(wrong, "@@frame@@", [good()])["e1"]["error"] == ex.E_NORESULT      # the right length, not the frame
    got = ex.read_pass('@@frame@@{"id": "e1", "result": {"ok": true, "value": 7}}\n@@frame@@{"id": "e1", "result": {"ok": true, "value": 8}}\n',
                       "@@frame@@", [good()])
    assert got["e1"]["value"] == 7                                            # the first line of an id counts
    got = ex.read_pass("@@frame@@not json\n@@frame@@{}\n", "@@frame@@", [good()])
    assert got["e1"]["error"] == ex.E_NORESULT


def test_a_result_that_differs_between_the_two_passes_is_an_error(tmp_path):
    out = evaluate(tmp_path, [good(setup="from shop.rules import roll", run="roll() > 0.0", expect=True),
                              good(id="e2", setup="from shop.rules import roll", run="round(roll(), 12)", expect=0.5)])
    assert statuses(out)["e2"] == "error" and "not deterministic" in out[1]["actual"]
    assert out[0]["status"] == "pass"                                          # a stable value from a random source passes


def test_a_timeout_is_an_error_not_a_hang(tmp_path, monkeypatch):
    monkeypatch.setattr(ex, "CHILD_TIMEOUT_S", 1)
    root = make_tree(tmp_path)
    argv, frame = ex.build_argv([good(setup="from shop.rules import spin", run="spin()", expect=1)], root=root,
                                child_timeout=1, python=sys.executable)
    out = ex.read_pass(runner(root)(argv)["stdout"], frame, [good()])
    assert out["e1"]["error"] == ex.E_TIMEOUT and out["e1"]["ok"] is False


def test_overrides_apply_to_a_module_constant_read_at_call_time(tmp_path):
    ov = good(tier="whatif", setup="from shop.rules import stop", run="stop(10.0, 1.0)", expect=8.5,
              overrides={"shop.rules.FLOOR": 1.0})
    out = evaluate(tmp_path, [ov])
    assert out[0]["status"] == "pass"
    out = evaluate(tmp_path, [ov], with_overrides=False)
    assert out[0]["status"] == "fail" and out[0]["actual"] == 50.0           # without the override: the real, current value


def test_an_override_does_not_reach_the_next_example(tmp_path):
    ov = good(tier="whatif", setup="from shop.rules import stop", run="stop(10.0, 1.0)", expect=8.5,
              overrides={"shop.rules.FLOOR": 1.0})
    plain = good(id="e2", setup="from shop.rules import stop", run="stop(10.0, 1.0)", expect=50.0)
    assert statuses(evaluate(tmp_path, [ov, plain])) == {"e1": "pass", "e2": "pass"}


def test_an_override_of_a_name_a_module_imported_by_value_changes_nothing_there(tmp_path):
    stale = good(tier="whatif", setup="from shop.user import floor_here", run="floor_here()", expect=50.0,
                 overrides={"shop.consts.FLOOR": 1.0})
    with_ov = evaluate(tmp_path, [stale])[0]
    without = evaluate(tmp_path, [stale], with_overrides=False)[0]
    assert with_ov["status"] == "pass" and with_ov["actual"] == 50.0 and without["actual"] == 50.0   # same with and without


@pytest.mark.parametrize("name", ["shop.rules.NO_SUCH", "no_such_module.X", "shop.rules"])
def test_an_override_of_a_name_that_does_not_exist_is_an_error(tmp_path, name):
    ov = good(tier="whatif", overrides={name: 1})
    out = evaluate(tmp_path, [ov])
    assert out[0]["status"] == "error"


def test_the_pass_without_overrides_ignores_them(tmp_path):
    ov = good(tier="whatif", setup="from shop.rules import stop", run="stop(10.0, 1.0)", expect=50.0,
              overrides={"shop.rules.NO_SUCH": 1})
    assert evaluate(tmp_path, [ov], with_overrides=False)[0]["status"] == "pass"


def test_each_example_runs_in_its_own_process(tmp_path):
    pollute = good(setup="import shop.rules as r\nr.FLOOR = 999.0", run="r.FLOOR", expect=999.0)
    after = good(id="e2", setup="import shop.rules as r", run="r.FLOOR", expect=50.0)
    assert statuses(evaluate(tmp_path, [pollute, after])) == {"e1": "pass", "e2": "pass"}


def test_the_runner_failing_is_raised_not_turned_into_a_result(tmp_path):
    def broken(argv):
        raise RuntimeError("sandbox is not available")
    with pytest.raises(RuntimeError, match="not available"):
        ex.evaluate([good()], broken, root=make_tree(tmp_path))


def test_a_runner_that_returns_nothing_gives_noresult(tmp_path):
    out = ex.evaluate([good()], lambda argv: {"stdout": ""}, root=make_tree(tmp_path))
    assert out[0]["status"] == "error" and ex.E_NORESULT in out[0]["actual"]
    out = ex.evaluate([good()], lambda argv: None, root=make_tree(tmp_path))
    assert out[0]["status"] == "error"


def test_the_argv_is_data_for_python_never_a_shell(tmp_path):
    argv, frame = ex.build_argv([good(setup="from shop.rules import blocked; import os")], root="/workspace")
    assert argv[:3] == ["python3", "-I", "-c"] and isinstance(argv[4], str) and "\x00" not in "".join(argv)
    payload = json.loads(argv[4])
    assert payload["root"] == "/workspace" and payload["frame"] == frame and len(payload["items"]) == 1
    assert payload["items"][0]["mark"].startswith("##") and payload["items"][0]["mark"] not in (frame, "")
    other, frame2 = ex.build_argv([good()], root="/workspace")
    assert frame2 != frame                                                      # a fresh nonce per pass


def test_a_timeout_through_evaluate_is_an_error_result(tmp_path, monkeypatch):
    monkeypatch.setattr(ex, "CHILD_TIMEOUT_S", 1)
    out = evaluate(tmp_path, [good(setup="from shop.rules import spin", run="spin()", expect=1), good(id="e2")])
    assert statuses(out) == {"e1": "error", "e2": "pass"} and ex.E_TIMEOUT in out[0]["actual"]


def test_sys_argv_is_cleaned_before_the_example_runs(tmp_path):
    out = evaluate(tmp_path, [good(setup="import sys\nfrom shop.rules import blocked", run="len(sys.argv)", expect=1)])
    assert out[0]["status"] == "pass"                                   # the payload (and its marks) was removed before the code ran


def test_output_without_a_newline_does_not_break_the_result(tmp_path):
    out = evaluate(tmp_path, [good(setup="import sys\nfrom shop.rules import blocked\nsys.stdout.write('no newline')\nsys.stderr.write('x')",
                                   run="blocked(50.0)", expect=True)])
    assert out[0]["status"] == "pass"


def test_a_file_of_the_tree_cannot_shadow_the_standard_library_in_the_runner(tmp_path):
    root = make_tree(tmp_path)
    (Path(root) / "json.py").write_text("raise RuntimeError('shadow')\n")
    out = ex.evaluate([good()], runner(root), root=root, python=sys.executable)
    assert out[0]["status"] == "pass"                                   # python -I: the tree is not on the path until the harness adds it


@pytest.mark.parametrize("value", [0, 0.0])
def test_zero_is_compared_exactly(value):
    assert ex.same(value, 0) and not ex.same(value, 1e-300) and not ex.same(1e-300, value)


# ---- review fixes (Opus diff review of PR 1) ---------------------------------------------------------------------------

def test_a_huge_int_is_compared_exactly_and_never_overflows():
    assert ex.same(10 ** 400, 10 ** 400) and not ex.same(10 ** 400, 10 ** 400 + 1)
    assert not ex.same(10 ** 400, 1.0) and not ex.same(1.0, 10 ** 400)
    assert ex.same(3, 3.0)


def test_a_huge_int_through_evaluate(tmp_path):
    out = evaluate(tmp_path, [good(setup="from shop.rules import blocked", run="10**400", expect=10 ** 400),
                              good(id="e2", setup="from shop.rules import blocked", run="10**400", expect=1.0)])
    assert statuses(out) == {"e1": "pass", "e2": "fail"}


def test_a_deeply_nested_expect_is_refused_by_parse():
    deep = []
    for _ in range(ex.MAX_DEPTH + 5):
        deep = [deep]
    assert any("nests more than" in p for p in ex.parse([good(expect=deep)])[1])
    ok = []
    for _ in range(10):
        ok = [ok]
    assert ex.parse([good(expect=ok)])[1] == []
    assert any("nests more than" in p for p in ex.parse([good(tier="whatif", overrides={"shop.rules.FLOOR": deep})])[1])


@pytest.mark.parametrize("depth", [1400, 20000])
def test_a_deep_actual_never_crashes_the_pass(tmp_path, depth):
    run = f"__import__('functools').reduce(lambda a, _: [a], range({depth}), [])"
    out = evaluate(tmp_path, [good(setup="from shop.rules import blocked", run=run, expect=1), good(id="e2")])
    assert out[0]["status"] in ("fail", "invalid", "error") and out[1]["status"] == "pass"      # the next example still ran
    assert len(json.dumps(out[0]["actual"])) <= ex.ACTUAL_MAX + 10


@pytest.mark.parametrize("raw", [[1], "x", 7, None, {"ok": True}, {"ok": False}, {"ok": False, "error": 5},
                                 {"ok": "yes", "value": 1}, {"ok": False, "invalid": True}])
def test_a_forged_or_damaged_result_counts_as_no_result(raw):
    line = "@@f@@" + json.dumps({"id": "e1", "result": raw}) + "\n"
    assert ex.read_pass(line, "@@f@@", [good()])["e1"]["error"] == ex.E_NORESULT


def test_a_well_formed_result_is_kept():
    for raw in ({"ok": True, "value": None}, {"ok": False, "error": "KeyError", "message": "k"},
                {"ok": False, "invalid": True, "type": "set"}):
        line = "@@f@@" + json.dumps({"id": "e1", "result": raw}) + "\n"
        assert ex.read_pass(line, "@@f@@", [good()])["e1"] == raw


def test_a_harness_error_name_cannot_be_the_expected_exception(tmp_path):
    base = {k: v for k, v in good().items() if k != "expect"}
    spin = {**base, "setup": "from shop.rules import spin", "run": "spin()"}
    for name in ("Timeout", "NoResult", "ValueError", "OSError"):
        assert ex.parse([{**spin, "raises": name}])[1] == []                   # a legal name...
    for bad in (ex.E_TIMEOUT, ex.E_NORESULT, ex.E_HARNESS):
        assert any("exception type" in p for p in ex.parse([{**spin, "raises": bad}])[1])


def test_a_timeout_never_satisfies_raises_timeout(tmp_path, monkeypatch):
    monkeypatch.setattr(ex, "CHILD_TIMEOUT_S", 1)
    base = {k: v for k, v in good().items() if k != "expect"}
    spin = {**base, "setup": "from shop.rules import spin", "run": "spin()", "raises": "Timeout"}
    out = evaluate(tmp_path, [spin])
    assert out[0]["status"] == "fail" and ex.E_TIMEOUT in out[0]["actual"]


def test_a_crashed_example_never_satisfies_raises_noresult(tmp_path):
    base = {k: v for k, v in good().items() if k != "expect"}
    kill = {**base, "setup": "import os\nfrom shop.rules import blocked", "run": "os._exit(3)", "raises": "NoResult"}
    out = evaluate(tmp_path, [kill])
    assert out[0]["status"] == "fail"


def test_a_value_over_the_line_limit_is_invalid_and_the_rest_of_the_pass_survives(tmp_path):
    big = good(setup="from shop.rules import blocked", run="'x' * 20000", expect="y")
    out = evaluate(tmp_path, [big, good(id="e2")])
    assert out[0]["status"] == "invalid" and "too large" in out[0]["actual"] and out[1]["status"] == "pass"


def test_two_runs_that_differ_only_in_the_message_are_the_same_result(tmp_path):
    base = {k: v for k, v in good().items() if k != "expect"}
    raising = {**base, "setup": "from shop.rules import blocked", "run": "(_ for _ in ()).throw(KeyError(object()))",
               "raises": "KeyError"}
    out = evaluate(tmp_path, [raising])
    assert out[0]["status"] == "pass"                                          # the address in the message changes between runs


def test_shown_cleans_the_texts_inside_a_short_value():
    assert ex.shown({"a": "\x1b[31mred\x00"}) == {"a": "[31mred"}
    assert ex.shown(["a\nb"]) == ["a b"]
    assert ex.shown({"k": 1.5, "n": None, "b": True}) == {"k": 1.5, "n": None, "b": True}


def test_noise_on_the_raw_stdout_does_not_break_the_result_line(tmp_path):
    noisy = good(setup="import os\nfrom shop.rules import blocked\nos.write(1, b'raw noise without a newline')", run="blocked(50.0)",
                 expect=True)
    assert evaluate(tmp_path, [noisy])[0]["status"] == "pass"


def test_a_mixed_key_object_does_not_make_parse_raise():
    out, problems = ex.parse([{**good(), 1: "x", "z": 2}])
    assert problems and out == []


def test_tautology_problem_does_not_raise_on_a_non_example(tmp_path):
    tree = make_tree(tmp_path)
    for bad in ({"id": "e1", "setup": 5, "run": "x"}, {"id": "e1"}, {"id": "e1", "setup": "x", "run": None}):
        assert ex.tautology_problem(bad, tree)


def test_a_relative_import_is_not_a_module_of_the_tree(tmp_path):
    tree = make_tree(tmp_path)
    assert "imports no module" in ex.tautology_problem(good(setup="from . import rules\nrules.blocked(1)", run="1+1"), tree)


def test_the_pass_timeout_leaves_room_for_every_child_and_the_start():
    assert ex.pass_timeout_s(6) == 6 * ex.CHILD_TIMEOUT_S + ex.PASS_SLACK_S and ex.pass_timeout_s(6) > 6 * ex.CHILD_TIMEOUT_S


def test_a_text_actual_is_cleaned_through_evaluate(tmp_path):
    out = evaluate(tmp_path, [good(setup="from shop.rules import blocked", run="'a\\x1b[0m' + 'b'", expect="z")])
    assert out[0]["status"] == "fail" and out[0]["actual"] == "a [0mb" and "\x1b" not in out[0]["actual"]


def test_shown_cleans_a_text():
    assert ex.shown("a\x1bb") == "a b" and ex.shown("x" * 400).endswith("...")


def test_a_relative_import_of_a_name_that_exists_at_the_root_is_still_not_a_module_of_the_tree(tmp_path):
    tree = make_tree(tmp_path)
    assert "imports no module" in ex.tautology_problem(good(setup="from .shop import rules\nrules.blocked(1)", run="1+1"), tree)
