"""SPEC_KARTU_SETUJU section 4 (PR 1 of T3): the mechanical derivation of an example as numbers (router/card_numbers.py).
A pure module: it parses text, it reads at most source files of a frozen tree through a callable, it runs nothing, it writes nothing,
it calls no model. Every test here builds the example as data and checks the exact card fields."""
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from router import card_numbers as cn  # noqa: E402

RM = (
    "from dataclasses import dataclass\n"
    "IDX_MIN_PRICE = 50\n"
    "@dataclass\n"
    "class Result:\n"
    "    passed: bool\n"
    "    reason: str\n"
    "    limit: float = 0.0\n"
    "def check_daily_loss_limit(realized_loss, capital, limit_pct, strict=False):\n    return 1\n"
    "def compute_position_size(*, ticker, capital_idr, entry_price, atr):\n    return 1\n"
    "def only_star(*args):\n    return 1\n"
    "def positional_only(a, b, /, c):\n    return 1\n"
)
SOURCES = {"risk_management.risk_manager": RM, "risk_management": "from risk_management.risk_manager import check_daily_loss_limit\n"}


def src(module):
    return SOURCES.get(module)


def ex(run, setup="from risk_management.risk_manager import check_daily_loss_limit", **kw):
    d = {"id": "e1", "tier": "same", "says": "x", "setup": setup, "run": run}
    d.update(kw if ("expect" in kw or "raises" in kw) else {"expect": True, **kw})
    return d


def derive(example, source_of=src):
    return cn.derive(example, source_of)


# ---- shapes of the grammar ----------------------------------------------------------------------------------------------

def test_call_positional_args_get_the_names_of_the_definition():
    c = derive(ex("check_daily_loss_limit(1_000_000, 100_000_000, 0.03).passed"))
    assert c["showable"] is True and c["why"] is None
    assert c["call"] == "risk_management.risk_manager.check_daily_loss_limit"
    assert [(i["name"], i["name_source"], i["value_json"], i["shown"]) for i in c["inputs"]] == [
        ("realized_loss", "def", "1000000", "1.000.000"),
        ("capital", "def", "100000000", "100.000.000"),
        ("limit_pct", "def", "0.03", "0,03"),
    ]
    assert c["output"] == [{"path": "passed", "label": "passed", "expect_json": "true", "shown": "ya (True)", "type": "bool"}]
    assert c["assumptions"] == []
    assert c["tier"] == "same" and c["id"] == "e1"


def test_keyword_args_keep_their_names():
    c = derive(ex("check_daily_loss_limit(realized_loss=5, capital=10, limit_pct=0.5, strict=True).passed"))
    assert [(i["name"], i["name_source"], i["shown"]) for i in c["inputs"]] == [
        ("realized_loss", "nama", "5"), ("capital", "nama", "10"), ("limit_pct", "nama", "0,5"), ("strict", "nama", "ya (True)")]
    assert c["showable"] is True


def test_mixed_positional_and_keyword():
    c = derive(ex("check_daily_loss_limit(7, 10, limit_pct=0.5).passed"))
    assert [(i["name"], i["name_source"]) for i in c["inputs"]] == [("realized_loss", "def"), ("capital", "def"), ("limit_pct", "nama")]


def test_attribute_chain_and_subscript_after_the_call():
    c = derive(ex("check_daily_loss_limit(1, 2, 3).reason", expect="ok text"))
    assert c["output"][0]["path"] == "reason" and c["output"][0]["shown"] == '"ok text"' and c["output"][0]["type"] == "text"
    c = derive(ex("check_daily_loss_limit(1, 2, 3)['k'].items[0]", expect=3))
    assert c["showable"] is True and c["output"][0]["path"] == '["k"].items[0]'


def test_bare_call_has_an_empty_path():
    c = derive(ex("check_daily_loss_limit(1, 2, 3)", expect=45.0))
    assert c["output"] == [{"path": "", "label": "", "expect_json": "45.0", "shown": "45,0", "type": "float"}]


def test_lambda_dict_projection_in_order():
    run = ("(lambda r: {'blocked': r.price_floor_blocked, 'shares': r.shares, 'stop': r.stop_loss_price})"
           "(rm.compute_position_size(ticker='TEST.JK', capital_idr=100_000_000, entry_price=50.0, atr=3.0))")
    c = derive(ex(run, setup="import risk_management.risk_manager as rm", expect={"blocked": False, "shares": 200000, "stop": 45}))
    assert c["showable"] is True
    assert c["call"] == "risk_management.risk_manager.compute_position_size"
    assert [(o["label"], o["path"], o["shown"], o["type"]) for o in c["output"]] == [
        ("blocked", "price_floor_blocked", "tidak (False)", "bool"),
        ("shares", "shares", "200.000", "int"),
        ("stop", "stop_loss_price", "45", "int")]
    assert [i["shown"] for i in c["inputs"]] == ['"TEST.JK"', "100.000.000", "50,0", "3,0"]


def test_lambda_tuple_projection():
    run = "(lambda r: (r.passed, r.limit))(check_daily_loss_limit(1, 2, 3))"
    c = derive(ex(run, expect=[True, 0.5]))
    assert [(o["path"], o["shown"]) for o in c["output"]] == [("passed", "ya (True)"), ("limit", "0,5")]


def test_raises_shows_the_error_name():
    c = derive(ex("check_daily_loss_limit(1, 0, 3).passed", raises="ZeroDivisionError"))
    assert c["showable"] is True and c["output"] == {"raises": "ZeroDivisionError", "shown": "gagal dengan ZeroDivisionError"}


def test_overrides_are_assumptions():
    c = derive(ex("check_daily_loss_limit(1, 2, 3).passed", tier="whatif",
                  overrides={"risk_management.risk_manager.IDX_MIN_PRICE": 1, "a.B": 0.5}))
    assert c["assumptions"] == [
        {"name": "risk_management.risk_manager.IDX_MIN_PRICE", "value_json": "1", "shown": "1"},
        {"name": "a.B", "value_json": "0.5", "shown": "0,5"}]
    assert c["tier"] == "whatif"


def test_the_display_name_is_the_resolved_name_not_the_alias():
    c = derive(ex("g(1, 2, 3).passed", setup="from risk_management.risk_manager import check_daily_loss_limit as g"))
    assert c["call"] == "risk_management.risk_manager.check_daily_loss_limit" and c["inputs"][0]["name"] == "realized_loss"
    c = derive(ex("rmm.check_daily_loss_limit(1, 2, 3).passed", setup="import risk_management.risk_manager as rmm"))
    assert c["call"] == "risk_management.risk_manager.check_daily_loss_limit"
    c = derive(ex("risk_management.risk_manager.check_daily_loss_limit(1, 2, 3).passed", setup="import risk_management.risk_manager"))
    assert c["call"] == "risk_management.risk_manager.check_daily_loss_limit" and c["showable"] is True


def test_several_import_lines():
    c = derive(ex("f(1, 2, 3).passed", setup="import risk_management\nfrom risk_management.risk_manager import check_daily_loss_limit as f"))
    assert c["showable"] is True


# ---- parameters from the definition ------------------------------------------------------------------------------------

def test_dataclass_fields_in_order_name_the_positional_args():
    c = derive(ex("Result(True, 'ok', 0.5).passed", setup="from risk_management.risk_manager import Result"))
    assert [(i["name"], i["name_source"]) for i in c["inputs"]] == [("passed", "def"), ("reason", "def"), ("limit", "def")]


def test_positional_only_and_keyword_only_parameters():
    c = derive(ex("positional_only(1, 2, 3)", setup="from risk_management.risk_manager import positional_only", expect=1))
    assert [i["name"] for i in c["inputs"]] == ["a", "b", "c"]
    c = derive(ex("compute_position_size(1, 2, 3, 4)", setup="from risk_management.risk_manager import compute_position_size", expect=1))
    assert c["showable"] is False and [i["name"] for i in c["inputs"]] == ["argumen 1", "argumen 2", "argumen 3", "argumen 4"]


def test_unresolved_positional_names_fall_back_and_close_the_card():
    for source_of in (lambda m: None, lambda m: "def other():\n    pass\n", lambda m: "def broken(:\n"):
        c = derive(ex("check_daily_loss_limit(1, 2, 3).passed"), source_of)
        assert c["showable"] is False and "argumen 1" in c["why"]
        assert [(i["name"], i["name_source"]) for i in c["inputs"]] == [
            ("argumen 1", "posisi"), ("argumen 2", "posisi"), ("argumen 3", "posisi")]


def test_reexport_through_a_package_is_not_resolved():
    c = derive(ex("check_daily_loss_limit(1, 2, 3).passed", setup="from risk_management import check_daily_loss_limit"))
    assert c["showable"] is False and c["inputs"][0]["name"] == "argumen 1"


def test_star_args_and_too_many_positionals_fall_back_for_the_extra():
    c = derive(ex("only_star(1, 2)", setup="from risk_management.risk_manager import only_star", expect=1))
    assert c["showable"] is False and [i["name"] for i in c["inputs"]] == ["argumen 1", "argumen 2"]
    c = derive(ex("check_daily_loss_limit(1, 2, 3, False, 5).passed"))
    assert [i["name"] for i in c["inputs"]][-1] == "argumen 5" and c["showable"] is False


def test_keyword_only_call_needs_no_definition():
    c = derive(ex("check_daily_loss_limit(realized_loss=1, capital=2, limit_pct=3).passed"), lambda m: None)
    assert c["showable"] is True


def test_decorated_functions_and_classes_with_bases_are_not_trusted_for_names():
    for text in ("import functools\n@functools.wraps(g)\ndef check_daily_loss_limit(a, b, c):\n    pass\n",
                 "class check_daily_loss_limit(Base):\n    def __init__(self, a, b, c):\n        pass\n",
                 "from dataclasses import dataclass\n@dataclass(kw_only=True)\nclass check_daily_loss_limit:\n    a: int\n"):
        c = derive(ex("check_daily_loss_limit(1, 2, 3).passed"), lambda m: text)
        assert c["showable"] is False and c["inputs"][0]["name"] == "argumen 1"
    init = "class check_daily_loss_limit:\n    def __init__(self, a, b):\n        pass\n"
    c = derive(ex("check_daily_loss_limit(1, 2).passed"), lambda m: init)
    assert [i["name"] for i in c["inputs"]] == ["a", "b"]
    fields = ("from dataclasses import dataclass, field\nfrom typing import ClassVar\n@dataclass\nclass check_daily_loss_limit:\n"
              "    a: int\n    K: ClassVar[int] = 3\n    hidden: int = field(init=False, default=0)\n    b: int = 0\n")
    c = derive(ex("check_daily_loss_limit(1, 2).passed"), lambda m: fields)
    assert [i["name"] for i in c["inputs"]] == ["a", "b"] and c["showable"] is True


REBOUND = [
    "def check_daily_loss_limit(a, b, c):\n    pass\ncheck_daily_loss_limit = lambda c, b, a: 0\n",
    "def check_daily_loss_limit(a, b, c):\n    pass\nfrom other import check_daily_loss_limit\n",
    "def check_daily_loss_limit(a, b, c):\n    pass\ntry:\n    from fast import check_daily_loss_limit\nexcept ImportError:\n    pass\n",
    "def check_daily_loss_limit(a, b, c):\n    pass\ndef check_daily_loss_limit(c, b, a):\n    pass\n",
    "if X:\n    def check_daily_loss_limit(a, b, c):\n        pass\n",
    "for check_daily_loss_limit in []:\n    pass\ndef check_daily_loss_limit(a, b, c):\n    pass\n",
    "def check_daily_loss_limit(a, b, c):\n    pass\nfrom other import *\n",
]


@pytest.mark.parametrize("text", REBOUND)
def test_a_rebound_or_conditional_name_is_not_trusted(text):
    c = derive(ex("check_daily_loss_limit(1, 2, 3).passed"), lambda m: text)
    assert c["showable"] is False and c["inputs"][0]["name"] == "argumen 1"


def test_a_name_inside_a_function_or_a_method_does_not_count_as_a_rebinding():
    text = "def check_daily_loss_limit(a, b, c):\n    check_daily_loss_limit = 1\nclass K:\n    def check_daily_loss_limit(self):\n        pass\n"
    c = derive(ex("check_daily_loss_limit(1, 2, 3).passed"), lambda m: text)
    assert c["showable"] is True and [i["name"] for i in c["inputs"]] == ["a", "b", "c"]


def test_class_decorators_and_dataclass_options():
    plain = "class check_daily_loss_limit:\n    def __init__(self, a, b):\n        pass\n"
    for deco in ("@register\n", "@wrap\n@dataclass\n", "@dataclass(init=False)\n", "@dataclass(kw_only=True)\n", "@dataclass(init=flag)\n", "@dataclass(frozen=flag)\n", "@dataclass(**kw)\n"):
        text = "from dataclasses import dataclass\n" + deco + plain
        assert derive(ex("check_daily_loss_limit(1, 2).passed"), lambda m: text)["showable"] is False, deco
    ok = "from dataclasses import dataclass\n@dataclass(frozen=True, order=False)\nclass check_daily_loss_limit:\n    a: int\n    b: int\n"
    assert [i["name"] for i in derive(ex("check_daily_loss_limit(1, 2).passed"), lambda m: ok)["inputs"]] == ["a", "b"]
    ok = "import dataclasses\n@dataclasses.dataclass\nclass check_daily_loss_limit:\n    a: int\n    b: int\n"
    assert derive(ex("check_daily_loss_limit(1, 2).passed"), lambda m: ok)["showable"] is True


def test_dataclass_fields_are_read_exactly_or_refused():
    head = "from dataclasses import dataclass, field, KW_ONLY\n@dataclass\nclass check_daily_loss_limit:\n"
    names = lambda body: [i["name"] for i in derive(ex("check_daily_loss_limit(1, 2).passed"), lambda m: head + body)["inputs"]]
    assert names("    a: NotClassVarish\n    b: int\n") == ["a", "b"]                         # not skipped by a substring
    assert names("    a: 'ClassVar[int]' = 3\n    b: int\n    c: int\n") == ["b", "c"]
    assert names("    a: int\n    _: KW_ONLY\n    b: int\n") == ["a", "argumen 2"]
    assert names("    a: int\n    b: int = field(kw_only=True)\n    c: int\n") == ["a", "c"]
    assert names("    a: int = field(init=1)\n    b: int\n") == ["argumen 1", "argumen 2"]       # not a literal bool: refuse, never skip
    assert names("    a: int = field(**kw)\n    b: int\n") == ["argumen 1", "argumen 2"]
    assert names("    if X:\n        a: int\n    b: int\n") == ["argumen 1", "argumen 2"]
    assert names("    a: int\n    b: int\n") == ["a", "b"]


def test_a_package_wins_over_a_module_and_a_standard_library_module_is_refused(tmp_path):
    root = tmp_path / "tree"
    (root / "p" / "x").mkdir(parents=True)
    (root / "p" / "__init__.py").write_text("")
    (root / "p" / "x.py").write_text("def f(a, b):\n    pass\n")
    (root / "p" / "x" / "__init__.py").write_text("def f(b, a):\n    pass\n")
    s = cn.tree_source_of(str(root))
    assert "def f(b, a)" in s("p.x")
    (root / "p" / "x" / "__init__.py").unlink()
    assert "def f(a, b)" in s("p.x")                               # a directory without __init__ is not a package
    for setup in ("from os import system", "import sys", "import os.path as op", "from dataclasses import dataclass"):
        c = derive(ex("system(1).x", setup=setup))
        assert c["showable"] is False and "standard library" in c["why"], setup


def test_a_keyword_that_repeats_a_positional_is_refused():
    c = derive(ex("check_daily_loss_limit(1, 2, 3, realized_loss=4).passed"))
    assert c["showable"] is False and "twice" in c["why"]


def test_id_tier_and_overrides_types_are_checked():
    for bad in ({"id": 5}, {"id": "x1"}, {"tier": "maybe"}, {"tier": None}, {"overrides": []}, {"overrides": ""}, {"overrides": 0},
                {"overrides": {"a.B": float("nan")}}, {"overrides": {1: 2}}):
        assert derive({**ex("check_daily_loss_limit(1, 2, 3).passed"), **bad})["showable"] is False, bad
    assert derive({**ex("check_daily_loss_limit(1, 2, 3).passed"), "overrides": None})["showable"] is True


def test_depth_and_size_limits_inside_the_text_limits_are_enforced():
    deep = "[" * 60 + "]" * 60                                       # 120 characters: within RUN_MAX, beyond MAX_DEPTH
    assert derive(ex("check_daily_loss_limit(%s, 2, 3).passed" % deep))["showable"] is False
    ok = "[" * 10 + "]" * 10
    assert derive(ex("check_daily_loss_limit(%s, 2, 3).passed" % ok))["showable"] is True
    assert derive(ex("check_daily_loss_limit(1, 2, 3).passed", setup="from risk_management.risk_manager import check_daily_loss_limit\n" + "#" * 700))["showable"] is False
    nested = []
    for _ in range(60):
        nested = [nested]
    assert derive(ex("check_daily_loss_limit(1, 2, 3).passed", expect=nested))["showable"] is False


def test_only_a_toplevel_definition_counts():
    nested = "class K:\n    def check_daily_loss_limit(self, a, b):\n        pass\n"
    c = derive(ex("check_daily_loss_limit(1, 2).passed"), lambda m: nested)
    assert c["showable"] is False


# ---- outside the grammar ------------------------------------------------------------------------------------------------

OUT = [
    ("setup is an assignment", dict(setup="from risk_management.risk_manager import check_daily_loss_limit\nIDX = 3")),
    ("setup patches a name", dict(setup="import risk_management.risk_manager as rm\nrm.IDX_MIN_PRICE = 1")),
    ("setup defines a function", dict(setup="from risk_management.risk_manager import check_daily_loss_limit\ndef f(): pass")),
    ("setup calls something", dict(setup="from risk_management.risk_manager import check_daily_loss_limit\nprint(1)")),
    ("setup with a relative import", dict(setup="from . import check_daily_loss_limit")),
    ("setup with a star import", dict(setup="from risk_management.risk_manager import *")),
    ("setup with a relative import of a module", dict(setup="from .risk_manager import check_daily_loss_limit")),
    ("a star import beside a good import", dict(setup="from x import *\nfrom risk_management.risk_manager import check_daily_loss_limit")),
    ("a bool index", dict(run="check_daily_loss_limit(1, 2, 3)[True]")),
    ("a float index", dict(run="check_daily_loss_limit(1, 2, 3)[1.5]")),
    ("a lambda applied to two calls", dict(run="(lambda r: {'a': r.x})(check_daily_loss_limit(1, 2, 3), check_daily_loss_limit(1, 2, 3))")),
    ("a lambda with a repeated key", dict(run="(lambda r: {'a': r.x, 'a': r.y})(check_daily_loss_limit(1, 2, 3))")),
    ("a lambda with an empty dict", dict(run="(lambda r: {})(check_daily_loss_limit(1, 2, 3))")),
    ("a lambda with an empty tuple", dict(run="(lambda r: ())(check_daily_loss_limit(1, 2, 3))")),
    ("setup is not python", dict(setup="from risk_management.risk_manager import (")),
    ("the same name bound twice", dict(setup="import a as check_daily_loss_limit\nfrom b import check_daily_loss_limit")),
    ("nested call in an argument", dict(run="check_daily_loss_limit(max(1, 2), 2, 3).passed")),
    ("a variable argument", dict(run="check_daily_loss_limit(x, 2, 3).passed")),
    ("an arithmetic argument", dict(run="check_daily_loss_limit(1 + 2, 2, 3).passed")),
    ("a tuple argument", dict(run="check_daily_loss_limit((1, 2), 2, 3).passed")),
    ("a complex argument", dict(run="check_daily_loss_limit(1j, 2, 3).passed")),
    ("a set argument", dict(run="check_daily_loss_limit({1}, 2, 3).passed")),
    ("a bytes argument", dict(run="check_daily_loss_limit(b'x', 2, 3).passed")),
    ("a dict with a number key", dict(run="check_daily_loss_limit({1: 2}, 2, 3).passed")),
    ("star args", dict(run="check_daily_loss_limit(*[1, 2, 3]).passed")),
    ("star star kwargs", dict(run="check_daily_loss_limit(**{'a': 1}).passed")),
    ("a comprehension", dict(run="[check_daily_loss_limit(i, 2, 3).passed for i in (1, 2)]")),
    ("a method on a call result", dict(run="check_daily_loss_limit(1, 2, 3).reason.upper()")),
    ("a name that is not imported", dict(run="other(1, 2, 3).passed")),
    ("no call at all", dict(run="3")),
    ("two calls", dict(run="check_daily_loss_limit(1, 2, 3).passed and check_daily_loss_limit(1, 2, 3).passed")),
    ("a lambda with two parameters", dict(run="(lambda r, s: {'a': r.x})(check_daily_loss_limit(1, 2, 3))")),
    ("a lambda that reads something else", dict(run="(lambda r: {'a': x.y})(check_daily_loss_limit(1, 2, 3))")),
    ("a lambda that calls in the body", dict(run="(lambda r: {'a': r.x()})(check_daily_loss_limit(1, 2, 3))")),
    ("a lambda with a default", dict(run="(lambda r=1: {'a': r.x})(check_daily_loss_limit(1, 2, 3))")),
    ("a lambda with a computed key", dict(run="(lambda r: {'a' + 'b': r.x})(check_daily_loss_limit(1, 2, 3))")),
    ("a lambda with arithmetic", dict(run="(lambda r: {'a': r.x + 1})(check_daily_loss_limit(1, 2, 3))")),
    ("a lambda returning a scalar", dict(run="(lambda r: r.x)(check_daily_loss_limit(1, 2, 3))")),
    ("a lambda over a nested call", dict(run="(lambda r: {'a': r.x})((lambda q: q)(1))")),
    ("run is not python", dict(run="check_daily_loss_limit(")),
    ("run is a statement", dict(run="x = check_daily_loss_limit(1, 2, 3)")),
    ("an await or a walrus", dict(run="(y := check_daily_loss_limit(1, 2, 3)).passed")),
    ("run is empty", dict(run="")),
]


def test_a_method_path_is_not_read_as_the_class():
    text = "class K:\n    def __init__(self, a, b):\n        pass\n    def m(self, c, d):\n        pass\n"
    c = derive(ex("K.m(1, 2).x", setup="from risk_management.risk_manager import K"),
               lambda m: text if m == "risk_management.risk_manager" else None)
    assert c["showable"] is False and c["inputs"][0]["name"] == "argumen 1"


def test_a_failing_reader_gives_no_names_not_a_crash():
    def boom(m):
        raise RuntimeError("boom")
    c = derive(ex("check_daily_loss_limit(1, 2, 3).passed"), boom)
    assert c["showable"] is False and c["inputs"][0]["name"] == "argumen 1" and c["call"]


def test_json_like_refuses_non_finite_numbers():
    assert cn._json_like(1.5) and not cn._json_like(float("inf")) and not cn._json_like([float("nan")]) and not cn._json_like({"a": float("-inf")})


@pytest.mark.parametrize("name,patch", OUT, ids=[n for n, _ in OUT])
def test_outside_the_grammar_is_not_showable_and_never_paraphrased(name, patch):
    example = ex("check_daily_loss_limit(1, 2, 3).passed")
    example.update(patch)
    if "lambda" in example["run"]:
        example["expect"] = {"a": 1}                   # a shape that would match, so the lambda itself is what is refused
    c = derive(example)
    assert c["showable"] is False
    assert c["why"] and "tidak bisa ditampilkan" in c["why"]
    assert c["inputs"] == [] and c["output"] is None and c["assumptions"] == [] and c["call"] is None
    assert "says" not in json.dumps({k: v for k, v in c.items() if k != "why"})


def test_lambda_expect_that_does_not_match_the_projection_is_not_showable():
    run = "(lambda r: {'a': r.x, 'b': r.y})(check_daily_loss_limit(1, 2, 3))"
    for expect in ({"a": 1}, {"a": 1, "b": 2, "c": 3}, [1, 2], 5):
        assert derive(ex(run, expect=expect))["showable"] is False
    assert derive(ex("(lambda r: (r.x, r.y))(check_daily_loss_limit(1, 2, 3))", expect=[1]))["showable"] is False
    assert derive(ex("(lambda r: (r.x, r.y))(check_daily_loss_limit(1, 2, 3))", expect={"x": 1}))["showable"] is False


def test_an_example_without_expect_or_raises_or_with_both_or_not_a_dict_is_not_showable():
    base = ex("check_daily_loss_limit(1, 2, 3).passed")
    del base["expect"]
    assert derive(base)["showable"] is False
    assert derive({**base, "expect": True, "raises": "X"})["showable"] is False
    assert derive({**base, "raises": "no good name"})["showable"] is False
    for junk in (None, [], "x", 5, {"id": "e1"}, {"id": "e1", "tier": "same", "setup": 3, "run": 4, "expect": 1}):
        c = derive(junk)
        assert c["showable"] is False and c["why"]
    assert derive({**ex("check_daily_loss_limit(1, 2, 3).passed"), "expect": None})["showable"] is True       # null is a value


def test_hostile_text_never_raises():
    deep = "(" * 4000 + "1" + ")" * 4000
    for run in (deep, "check_daily_loss_limit(" + "[" * 3000 + "]" * 3000 + ", 2, 3).passed", "x" * 5000, "\x00", "1" * 100000):
        c = derive(ex(run))
        assert c["showable"] is False
    c = derive(ex("check_daily_loss_limit(1, 2, 3).passed", setup="import " + "a." * 2000 + "b"))
    assert c["showable"] is False
    assert derive(ex("check_daily_loss_limit(1, 2, 3).passed"), lambda m: (_ for _ in ()).throw(RuntimeError("boom")))["showable"] is False


def test_over_the_size_limits_is_not_showable():
    big = "[" + ",".join(["1"] * 400) + "]"
    c = derive(ex("check_daily_loss_limit(%s, 2, 3).passed" % big))
    assert c["showable"] is False


# ---- number format ------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("value,shown", [
    (0, "0"), (45, "45"), (45.0, "45,0"), (-45, "-45"), (-45.5, "-45,5"), (1000, "1.000"), (1_000_000, "1.000.000"),
    (-1_234_567, "-1.234.567"), (999, "999"), (0.03, "0,03"), (0.1, "0,1"), (1e-05, "1e-05"), (1.5e300, "1,5e+300"), (1.5e-05, "1,5e-05"), (-2.5e-10, "-2,5e-10"),
    (1e16, "1e+16"), (-0.0, "-0,0"), (0.0, "0,0"), (123456789.5, "123456789,5"), (2 ** 53, "9.007.199.254.740.992"),
    (2 ** 53 + 1, "9.007.199.254.740.993"), (10 ** 20, "100.000.000.000.000.000.000"), (True, "ya (True)"), (False, "tidak (False)"),
    (None, "kosong (None)"), ("Rp1,000,000", '"Rp1,000,000"'), ("1.000.000", '"1.000.000"'), ("", '""'), ("a\"b", '"a\\"b"'),
    ("é", '"é"'),
])
def test_scalar_format(value, shown):
    assert cn.fmt(value) == shown


def test_forty_five_and_forty_five_point_zero_are_not_the_same_on_the_card():
    a = derive(ex("check_daily_loss_limit(1, 2, 3).limit", expect=45))["output"][0]
    b = derive(ex("check_daily_loss_limit(1, 2, 3).limit", expect=45.0))["output"][0]
    assert (a["shown"], a["expect_json"], a["type"]) == ("45", "45", "int")
    assert (b["shown"], b["expect_json"], b["type"]) == ("45,0", "45.0", "float")


def test_text_is_never_reformatted():
    c = derive(ex("check_daily_loss_limit(1, 2, 3).reason", expect="Daily realized loss Rp1,000,000 within 3% limit (Rp3,000,000)"))
    assert c["output"][0]["shown"] == '"Daily realized loss Rp1,000,000 within 3% limit (Rp3,000,000)"'
    assert "1.000.000" not in c["output"][0]["shown"]


def test_numbers_are_never_rounded():
    c = derive(ex("check_daily_loss_limit(0.1234567890123456, 2, 3).limit", expect=0.30000000000000004))
    assert c["inputs"][0]["shown"] == "0,1234567890123456" and c["output"][0]["shown"] == "0,30000000000000004"


def test_lists_and_dicts_one_element_per_line_nested():
    assert cn.fmt([]) == "[]" and cn.fmt({}) == "{}"
    assert cn.fmt([1, 2.5, "a"]) == '[\n  1\n  2,5\n  "a"\n]'
    assert cn.fmt({"a": 1000, "b": [True, None]}) == '{\n  "a": 1.000\n  "b": [\n    ya (True)\n    kosong (None)\n  ]\n}'
    c = derive(ex("check_daily_loss_limit([1, 2], {'k': 3}, 3).passed"))
    assert c["inputs"][0]["shown"] == "[\n  1\n  2\n]" and c["inputs"][1]["shown"] == '{\n  "k": 3\n}'


def test_one_changed_literal_changes_exactly_one_number_on_the_card():
    base = derive(ex("check_daily_loss_limit(1_000_000, 100_000_000, 0.03).passed"))
    for n, repl in ((0, "2_000_000"), (1, "200_000_000"), (2, "0.04")):
        args = ["1_000_000", "100_000_000", "0.03"]
        args[n] = repl
        changed = derive(ex("check_daily_loss_limit(%s).passed" % ", ".join(args)))
        diff = [k for k in range(3) if base["inputs"][k] != changed["inputs"][k]]
        assert diff == [n] and base["output"] == changed["output"] and base["call"] == changed["call"]
    changed = derive(ex("check_daily_loss_limit(1_000_000, 100_000_000, 0.03).passed", expect=False))
    assert changed["inputs"] == base["inputs"] and changed["output"] != base["output"]


def test_the_card_is_json_and_deterministic():
    example = ex("check_daily_loss_limit(1, 2, 3).passed")
    a, b = derive(example), derive(json.loads(json.dumps(example)))
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_the_example_is_not_changed():
    example = ex("check_daily_loss_limit(1, 2, 3).passed", overrides={"a.B": 1}, tier="whatif")
    before = json.dumps(example, sort_keys=True)
    derive(example)
    assert json.dumps(example, sort_keys=True) == before


# ---- the frozen tree reader ---------------------------------------------------------------------------------------------

def tree(tmp_path):
    root = tmp_path / "tree"
    (root / "pkg" / "sub").mkdir(parents=True)
    (root / "pkg" / "__init__.py").write_text("")
    (root / "pkg" / "sub" / "mod.py").write_text("def f(a, b):\n    return a\n")
    (root / "single.py").write_text("def g(x):\n    return x\n")
    return root


def test_tree_source_of_reads_modules_and_packages(tmp_path):
    s = cn.tree_source_of(str(tree(tmp_path)))
    assert "def f" in s("pkg.sub.mod") and "def g" in s("single") and s("pkg") == "" and s("nope") is None and s("pkg.nope") is None
    c = derive(ex("f(1, 2)", setup="from pkg.sub.mod import f", expect=1), s)
    assert [i["name"] for i in c["inputs"]] == ["a", "b"] and c["showable"] is True


def test_tree_source_of_refuses_bad_names_links_and_big_files(tmp_path):
    root = tree(tmp_path)
    outside = tmp_path / "outside.py"
    outside.write_text("def secret(a):\n    pass\n")
    os.symlink(outside, root / "linked.py")
    os.symlink(tmp_path, root / "dirlink")
    (root / "big.py").write_text("x = 1\n" * 200_000)
    (root / "fifo.py").write_text("")
    os.remove(root / "fifo.py")
    os.mkfifo(root / "fifo.py")
    s = cn.tree_source_of(str(root))
    for name in ("linked", "dirlink.outside", "big", "fifo", "..", "../outside", "pkg/sub", "pkg..sub", "", ".x", "a b", "pkg.sub.mod\x00", "é"):
        assert s(name) is None, name
    assert s(5) is None and s(None) is None


def test_the_module_runs_and_writes_nothing():
    import re
    text = Path(cn.__file__).read_text()
    for banned in ("subprocess", "socket", "urllib", "requests", "__import__", "importlib", "os.system", "os.write", "os.remove", "os.rename",
                   "O_WRONLY", "O_RDWR", "O_CREAT", "harness", "from models", "import models"):
        assert banned not in text, banned
    assert not re.search(r"(?<![\w.])(exec|eval|compile|open)\(", text)           # the builtins; ast.literal_eval and os.open are not them
    assert "ast.literal_eval" in text and "O_NOFOLLOW" in text
