"""SPEC_INSERT_INTO (docs/reviews/SPEC_INSERT_INTO.md): a changed_tests entry may carry `into_class` with `append`: the harness puts the
block at the end of that top-level class of the intake file. The pieces: the builder (acceptance/changed.py from_append), the
structural predicate `insertion`, the whitelist of the inserted statements, the inherited-name check on the collection, the
sizes, the drafter's arguments and the draft review, and the tightened check of an append at the end of a file. Nothing here
needs a sandbox (the real run is in test_insert_into_sandbox.py)."""
import ast
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_append_tests as ta  # noqa: E402
import test_drafter as td  # noqa: E402
from acceptance import changed as ch  # noqa: E402
from acceptance import draft as dr  # noqa: E402
from acceptance import intake  # noqa: E402
from codetask import drafter  # noqa: E402

PATH = ta.PATH
OLD2 = '''import unittest
from lib import f


class MixinTests:
    def test_inherited(self):
        pass


class AlphaTests(unittest.TestCase):
    """doc"""

    def test_a(self):
        self.assertEqual(f(1), 1)

    def test_b(self):
        self.assertEqual(f(2), 2)


# a comment after alpha
class BetaTests(MixinTests, unittest.TestCase):
    def test_c(self):
        pass


if __name__ == "__main__":
    unittest.main()
'''
BLOCK = "def test_new(self):\n    self.assertEqual(f(3), 4)\n"
INSERTED = "\n    def test_new(self):\n        self.assertEqual(f(3), 4)\n"
AFTER_B = "        self.assertEqual(f(2), 2)\n"
EXPECTED = OLD2.replace(AFTER_B, AFTER_B + INSERTED, 1)
NODE = f"{PATH}::AlphaTests::test_new"
OLDX = ("import unittest\nfrom lib import f, ImportedMixin\n\n\nclass AlphaTests(unittest.TestCase):\n    def test_a(self):\n        pass\n\n\n"
        "class BetaTests(ImportedMixin, unittest.TestCase):\n    def test_c(self):\n        pass\n")     # the base class lives in another file


def build(into="AlphaTests", block=BLOCK, old=OLD2, **extra):
    e = {"path": PATH, "append": block, **({"into_class": into} if into is not None else {}), **extra}
    return ch.from_append([e], {PATH: old}.get, intake._plain)


def refused(*a, **k):
    out, problems = build(*a, **k)
    assert out == [] and problems, (out, problems)
    return " | ".join(problems)


# ---- the builder -------------------------------------------------------------------------------------------------------------


def test_the_block_goes_to_the_end_of_the_class_with_one_blank_line_before_it():
    out, problems = build()
    assert problems == [] and out == [{"path": PATH, "content": EXPECTED}]
    assert "into_class" not in out[0] and "append" not in out[0]


def test_what_follows_the_class_stays_after_the_block_comments_and_main_guard_included():
    content = build()[0][0]["content"]
    assert content.index("def test_new") < content.index("# a comment after alpha") < content.index('if __name__ == "__main__"')


def test_a_block_that_is_already_indented_is_dedented_first():
    assert build(block="    def test_new(self):\n        self.assertEqual(f(3), 4)\n")[0][0]["content"] == EXPECTED
    assert build(block="\n\n" + BLOCK + "\n\n\n")[0][0]["content"] == EXPECTED


def test_the_last_class_before_a_main_guard_takes_a_block_and_the_guard_stays():
    out, problems = build(into="BetaTests")
    c = out[0]["content"]
    assert problems == [] and c.index("def test_new") < c.index('if __name__ == "__main__"')
    assert c.rstrip().endswith("unittest.main()")


@pytest.mark.parametrize("tail", ["", "\n", "\n\n\n"])
def test_the_last_class_of_a_file_with_or_without_final_newlines(tail):
    old = "import unittest\nfrom lib import f\n\n\nclass A(unittest.TestCase):\n    def test_x(self):\n        pass" + tail
    out, problems = build(into="A", old=old)
    assert problems == []
    c = out[0]["content"]
    assert c.endswith("\n") and c.count("def test_new") == 1
    ast.parse(c)
    assert ch.insertion(old, c)["class"] == "A"


def test_a_decorated_old_method_does_not_move_the_block():
    old = "import unittest\n\n\nclass A(unittest.TestCase):\n    @unittest.skip('x')\n    def test_x(self):\n        pass\n"
    c = build(into="A", old=old)[0][0]["content"]
    assert c == old + "\n    def test_new(self):\n        self.assertEqual(f(3), 4)\n"


@pytest.mark.parametrize("extra, why", [
    ({"content": "x = 1\n"}, "exactly one"),
    ({"removed": [{"node": "test_a", "reason": "r"}]}, "removed and modified"),
    ({"modified": [{"node": "test_a", "reason": "r"}]}, "removed and modified"),
])
def test_the_form_is_refused(extra, why):
    assert why in refused(**extra)


@pytest.mark.parametrize("into", ["", "A.B", "1x", "x y", "A" * 101, "AlphaTests()", "Alpha-Tests"])
def test_a_class_name_that_is_not_an_identifier_is_refused(into):
    assert "into_class" in refused(into=into)


def test_a_none_into_class_is_a_model_dump_and_means_an_ordinary_append_at_the_end():
    block = "class N(unittest.TestCase):\n    def test_n(self):\n        pass\n"
    out, problems = ch.from_append([{"path": PATH, "append": block, "into_class": None}], {PATH: ta.OLD}.get, intake._plain)
    plain, _ = ch.from_append([{"path": PATH, "append": block}], {PATH: ta.OLD}.get, intake._plain)
    assert out == plain and problems == [] and out[0]["content"].endswith("pass\n")


def test_into_class_with_a_blank_block_is_refused_as_any_append():
    assert "non-empty" in refused(block="  \n")


def test_a_class_the_file_does_not_define_is_refused():
    assert "NoSuchTests" in refused(into="NoSuchTests")


def test_a_class_defined_twice_is_refused():
    assert "AlphaTests" in refused(old=OLD2 + "\n\nclass AlphaTests(unittest.TestCase):\n    def test_z(self):\n        pass\n")


@pytest.mark.parametrize("old", [
    OLD2.replace("\n\nif __name__", "\n\nAlphaTests = deco(AlphaTests)\n\n\nif __name__", 1),            # rebound later
    OLD2.replace("\n\nif __name__", "\n\ndel AlphaTests\n\n\nif __name__", 1),
    OLD2.replace("\n\nif __name__", "\n\nfrom other import AlphaTests\n\n\nif __name__", 1),
    OLD2.replace("\n\nif __name__", "\n\ndef AlphaTests():\n    pass\n\n\nif __name__", 1),
    "import unittest\n\nif True:\n    class AlphaTests(unittest.TestCase):\n        def test_a(self):\n            pass\n",   # not top level
    OLD2.replace("\n\nif __name__", "\n\ntry:\n    pass\nexcept ValueError as AlphaTests:\n    pass\n\n\nif __name__", 1),
    "import unittest\n\ntry:\n    class AlphaTests(unittest.TestCase):\n        def test_a(self):\n            pass\nexcept ImportError:\n    pass\n",
    "import unittest\n\n\nclass Outer:\n    class AlphaTests(unittest.TestCase):\n        def test_a(self):\n            pass\n",
])
def test_a_class_name_that_is_bound_more_than_once_or_not_at_the_top_level_is_refused(old):
    assert "AlphaTests" in refused(old=old)


def test_a_decorated_class_is_refused():
    old = "import unittest\n\n\n@unittest.skipIf(False, 'x')\nclass AlphaTests(unittest.TestCase):\n    def test_a(self):\n        pass\n"
    assert "decorator" in refused(old=old)


def test_a_one_line_class_is_refused():
    assert "AlphaTests" in refused(old="import unittest\n\n\nclass AlphaTests(unittest.TestCase): pass\n")


def test_a_class_body_indented_with_tabs_is_refused():
    old = "import unittest\n\n\nclass A(unittest.TestCase):\n\tdef test_x(self):\n\t\tpass\n"
    assert "tab" in refused(into="A", old=old).lower()


@pytest.mark.parametrize("bad", ["\r", "\x0c", "\x0b"])
def test_carriage_returns_form_feeds_and_vertical_tabs_are_refused_in_the_file_and_in_the_block(bad):
    assert refused(old=OLD2.replace("# a comment after alpha", f"# a comment{bad}after alpha", 1))
    assert refused(block=BLOCK.replace("f(3)", f"f(3){bad}", 1))
    assert refused(old=OLD2.replace("\n", "\r\n")) if bad == "\r" else True


def test_the_file_is_split_on_newlines_only_so_a_unicode_line_separator_in_a_string_cannot_shift_the_line_numbers():
    old = OLD2.replace('"""doc"""', '"""a\u2028b\x85c\x1cd"""', 1)
    out, problems = build(old=old)
    assert problems == [] and ch.insertion(old, out[0]["content"])["class"] == "AlphaTests"


# ---- what a block may hold (route independent) -------------------------------------------------------------------------------


@pytest.mark.parametrize("block, why", [
    ("def helper(self):\n    return 1\n", "test"),                                    # not a test
    ("x = 1\n\ndef test_a2(self):\n    pass\n", "test"),                             # a class-level assignment
    ("@staticmethod\ndef test_s():\n    pass\n", "decorator"),
    ("def test_a2(self, v=object()):\n    pass\n", "constant"),
    ("def test_a2(self, v=[1]):\n    pass\n", "constant"),
    ("def test_a2(self, *, v=object()):\n    pass\n", "constant"),
    ("def test_a2(self, v=(1, object())):\n    pass\n", "constant"),
    ("def setUp(self):\n    pass\n", "test"),
    ("def setUpClass(cls):\n    pass\n", "test"),
    ("def run(self, result=None):\n    pass\n", "test"),
    ("def __init__(self):\n    pass\n", "test"),
    ("def __getattribute__(self, n):\n    pass\n", "test"),
    ("def test_a2(self):\n    pass\n\nclass Inner:\n    pass\n", "test"),
    ("import os\n\ndef test_a2(self):\n    pass\n", "test"),
    ("print('x')\n", "test"),
    ("# only a comment\n", "non-empty"),
    ("", "non-empty"),
    ("def test_a2(self):\n    pass\n\ndef test_a2(self):\n    pass\n", "twice"),
    ("def test_a(self):\n    pass\n", "already"),                                       # a name the class has
])
def test_the_block_holds_only_test_methods_with_new_names_no_decorators_and_constant_defaults(block, why):
    assert why in refused(block=block)


def test_async_test_methods_and_constant_defaults_are_fine():
    out, problems = build(block="async def test_x(self, a=1, *, b='s', c=None):\n    pass\n\ndef test_y(self, t=(1, 2)):\n    pass\n")
    assert problems == [], problems


def test_the_whitelist_holds_for_a_content_draft_too_the_route_does_not_matter():
    helper = EXPECTED.replace("def test_new(self):", "def helper(self):", 1)
    ins = ch.insertion(OLD2, helper)
    assert ins and ins["kind"] == "class"
    assert any("test" in p for p in ch.insertion_problems(PATH, OLD2, ins))
    assert ch.insertion_problems(PATH, OLD2, ch.insertion(OLD2, EXPECTED)) == []


def test_a_name_collected_from_the_intake_for_that_class_is_refused_for_a_base_class_of_another_file():
    out, problems = build(into="BetaTests", old=OLDX, block="def test_inherited(self):\n    pass\n")
    assert problems == []              # the class body and the bases of this file do not have it: only the collection can know
    ins = ch.insertion(OLDX, out[0]["content"])
    before = {f"{PATH}::BetaTests::test_inherited", f"{PATH}::BetaTests::test_c", f"{PATH}::ImportedMixin::test_inherited"}
    assert any("test_inherited" in p and "BetaTests" in p for p in ch.inherited_problems(PATH, ins, before))
    assert ch.inherited_problems(PATH, ch.insertion(OLD2, EXPECTED), before) == []


def test_an_inherited_test_of_a_base_class_in_the_same_file_is_refused_by_the_builder_itself():
    assert "already" in refused(into="BetaTests", block="def test_inherited(self):\n    pass\n")


# ---- re-indenting must not change what the block says -------------------------------------------------------------------------


@pytest.mark.parametrize("block", [
    'def test_s(self):\n    s = """a\nb\n"""\n    self.assertEqual(s, "x")\n',          # the string would gain the indentation
    'def test_s(self):\n    s = "a\\\nb"\n    self.assertEqual(s, "x")\n',              # a continuation line
])
def test_a_block_whose_strings_would_change_under_the_new_indentation_is_refused(block):
    assert "string" in refused(block=block).lower() or "indent" in refused(block=block).lower()


def test_a_block_already_indented_like_methods_is_fine_when_its_strings_do_not_depend_on_the_indentation():
    block = '    def test_s(self):\n        s = "a b"\n        self.assertEqual(s, "x")\n'
    out, problems = build(block=block)
    assert problems == [] and 's = "a b"' in out[0]["content"], problems


def test_a_multi_line_string_whose_value_depends_on_the_margin_is_refused_however_the_block_is_indented():
    block = '    def test_s(self):\n        s = """a\n    b\n    """\n        self.assertEqual(s, "x")\n'
    assert "string" in refused(block=block).lower()


# ---- the structural predicate -------------------------------------------------------------------------------------------------


def test_an_append_at_the_end_is_an_insertion_of_kind_end():
    new = OLD2.rstrip("\n") + "\n\n\nclass N(unittest.TestCase):\n    def test_n(self):\n        pass\n"
    assert ch.insertion(OLD2, new) == {"kind": "end"}


def test_methods_added_at_the_end_of_one_class_are_an_insertion_of_kind_class():
    ins = ch.insertion(OLD2, EXPECTED)
    assert ins["kind"] == "class" and ins["class"] == "AlphaTests" and [s.name for s in ins["stmts"]] == ["test_new"]


def test_the_region_of_an_insertion_is_exactly_the_inserted_methods_which_is_what_the_review_shows():
    ins = ch.insertion(OLD2, EXPECTED)
    assert "\n".join(EXPECTED.split("\n")[ins["first"] - 1:ins["last"]]) == INSERTED.strip("\n")
    trailing = EXPECTED.replace(INSERTED, INSERTED + "    # a trailing comment of the block\n", 1)
    t = ch.insertion(OLD2, trailing)
    assert t and "\n".join(trailing.split("\n")[t["first"] - 1:t["last"]]).endswith("# a trailing comment of the block")


def test_the_region_is_found_by_structure_not_by_text_offset():
    # Opus' counterexample: a text diff of this insertion before "\n    def test_c" is not parsable; the AST one is
    old = "class T:\n    def test_a(self):\n        pass\n\n    def test_c(self):\n        pass\n"
    new = old + "\n    def test_a2(self):\n        pass\n"
    ins = ch.insertion(old, new)
    assert ins and [s.name for s in ins["stmts"]] == ["test_a2"]
    mid = "class T:\n    def test_a(self):\n        pass\n\n    def test_a2(self):\n        pass\n\n    def test_c(self):\n        pass\n"
    assert ch.insertion(old, mid) is None                    # not at the end of the body


@pytest.mark.parametrize("new", [
    EXPECTED.replace("import unittest\n", "import unittest\n\n\nclass TestCase(unittest.TestCase):\n    def run(self, result=None):\n        pass\n", 1),
    EXPECTED.replace("def test_a(self):", "def test_a2(self):\n        pass\n\n    def test_a(self):", 1),         # inside the class, not at its end
    EXPECTED.replace("self.assertEqual(f(1), 1)", "self.assertEqual(f(1), 2)", 1),                                   # an old test changes
    EXPECTED.replace("class AlphaTests(unittest.TestCase)", "class AlphaTests(unittest.TestCase, Other)", 1),         # the bases change
    EXPECTED + "\n\ndef helper():\n    pass\n",                                                                       # one more at the module's end too
    EXPECTED.replace("class BetaTests", "def stray():\n    pass\n\n\nclass BetaTests", 1),
    OLD2.replace("    def test_b(self):\n        self.assertEqual(f(2), 2)\n", "", 1),                                # a test is removed
])
def test_anything_but_methods_added_at_the_end_of_one_class_is_not_an_insertion(new):
    got = ch.insertion(OLD2, new)
    assert got is None or got["kind"] == "end"          # never a class insertion: that is what the whitelist and K1 rest on


def test_methods_added_to_two_classes_are_not_an_insertion():
    both = EXPECTED.replace("    def test_c(self):\n        pass\n", "    def test_c(self):\n        pass\n\n    def test_c2(self):\n        pass\n", 1)
    assert both != EXPECTED and ch.insertion(OLD2, both) is None


def test_a_file_that_does_not_parse_is_no_insertion():
    assert ch.insertion(OLD2, EXPECTED + "def (") is None and ch.insertion("def (", EXPECTED) is None


def test_the_text_must_be_the_old_text_plus_the_added_lines_only():
    # the AST is the same but a comment of the old file went missing: the text is not an insertion of those lines
    assert ch.insertion(OLD2, EXPECTED.replace("# a comment after alpha\n", "", 1)) is None


# ---- sizes and the draft-level checks ------------------------------------------------------------------------------------------


def test_the_bytes_added_by_an_insertion_are_the_difference_of_the_two_texts():
    assert ch.insertion_bytes(OLD2, EXPECTED) == len(EXPECTED.encode()) - len(OLD2.encode())
    end = OLD2.rstrip("\n") + "\n\n\nclass N:\n    pass\n"
    assert ch.insertion_bytes(OLD2, end) == ch.added_bytes(OLD2, end)


def test_a_block_of_exactly_the_limit_is_accepted_and_one_more_byte_is_not():
    head = "def test_big(self):\n    pass\n    # "
    n = ch.MAX_BLOCK_BYTES - len(head.encode()) - 1
    exact = head + "x" * n + "\n"
    assert len(exact.encode()) == ch.MAX_BLOCK_BYTES
    assert build(block=exact)[1] == []
    assert "larger" in refused(block=exact + "x")


def statics_of(content, must=(NODE,), old=OLD2):
    return ta.statics(ta.draft_of(content, must=must), old)


def test_a_draft_of_a_class_insertion_needs_no_new_test_file_and_no_redefinition_check_on_the_indented_tail():
    probs = statics_of(EXPECTED)
    assert not any("only adds tests" in p or "does not parse on its own" in p or "redefines" in p for p in probs), probs


def test_a_class_insertion_into_the_last_class_of_the_file_is_not_refused_for_its_indented_tail():
    old = "import unittest\n\n\nclass AlphaTests(unittest.TestCase):\n    def test_a(self):\n        pass\n"
    content = old + INSERTED
    probs = ta.statics(ta.draft_of(content, must=(NODE,)), old)
    assert not any("does not parse on its own" in p or "only adds tests" in p for p in probs), probs


def test_a_draft_without_new_tests_still_needs_a_required_node_that_is_new():
    probs = statics_of(EXPECTED, must=(f"{PATH}::AlphaTests::test_a",))
    assert any("only adds tests" in p for p in probs)


def test_the_size_rule_counts_the_added_region_of_an_insertion():
    big = "    # " + "x" * 60_000 + "\n"
    content = OLD2.replace(AFTER_B, AFTER_B + "\n    def test_new(self):\n" + big + "        pass\n", 1)
    assert any("larger than" in p for p in statics_of(content))


def test_a_content_draft_that_inserts_helper_code_into_a_class_is_refused_like_a_block():
    content = EXPECTED.replace("def test_new(self):", "def setUp(self):", 1)
    assert any("test" in p and "AlphaTests" in p for p in statics_of(content, must=()))


def test_k1_holds_for_an_insertion_a_required_node_must_be_new(tmp_path):
    d = ta.draft_of(EXPECTED, must=(f"{PATH}::AlphaTests::test_a",))
    got = ta.k1(tmp_path / "one", d, OLD2, {f"{PATH}::AlphaTests::test_a", f"{PATH}::AlphaTests::test_b"},
                {f"{PATH}::AlphaTests::test_a", f"{PATH}::AlphaTests::test_b", NODE})
    assert any("already a test" in p for p in got)
    d2 = ta.draft_of(EXPECTED, must=(NODE,))
    assert ta.k1(tmp_path / "two", d2, OLD2, {f"{PATH}::AlphaTests::test_a"}, {f"{PATH}::AlphaTests::test_a", NODE}) == []


def test_k1_refuses_a_new_method_that_overrides_an_inherited_test(tmp_path):
    out, _ = build(into="BetaTests", old=OLDX, block="def test_inherited(self):\n    self.assertEqual(1, 2)\n")
    d = ta.draft_of(out[0]["content"], must=(f"{PATH}::BetaTests::test_inherited",))
    got = ta.k1(tmp_path, d, OLDX, {f"{PATH}::BetaTests::test_inherited", f"{PATH}::BetaTests::test_c"},
                {f"{PATH}::BetaTests::test_inherited", f"{PATH}::BetaTests::test_c"})
    assert any("test_inherited" in p for p in got)


def test_k1_still_refuses_a_lost_test_for_an_insertion(tmp_path):
    d = ta.draft_of(EXPECTED, must=(NODE,))
    got = ta.k1(tmp_path, d, OLD2, {f"{PATH}::AlphaTests::test_a", f"{PATH}::AlphaTests::test_b"}, {NODE})
    assert any("loses" in p for p in got), got


# ---- the draft is the same whichever route made it -------------------------------------------------------------------------------


def test_an_insertion_by_into_class_and_the_equal_content_have_the_same_sha(tmp_path):
    root = ta.intake_dir_of(tmp_path, OLD2)
    a = ta.args_for(append=BLOCK, into_class="AlphaTests")
    a["validation"] = [{"id": "target", "paths": [PATH], "must_pass": [NODE], "min_tests": 1}]
    da, pa = drafter.draft_from_args(a, base="shop", policy=td.POLICY, intake_dir=root)
    b = ta.args_for(content=EXPECTED)
    b["validation"] = a["validation"]
    db, pb = drafter.draft_from_args(b, base="shop", policy=td.POLICY, intake_dir=root)
    assert pa == [] and pb == [], (pa, pb)
    sha = lambda d: ta.hashlib.sha256(ta.ct.canonical(d).encode()).hexdigest()    # noqa: E731
    assert da["changed_tests"] == db["changed_tests"] == [{"path": PATH, "content": EXPECTED}]
    assert da == db and sha(da) == sha(db)


def test_the_schema_knows_into_class_and_a_none_is_a_model_dump_not_a_mode():
    f = drafter.ChangedTest.model_fields
    assert "into_class" in f and f["into_class"].default is None
    assert drafter.ChangedTest(path="p", append="x", into_class=None).model_dump()["into_class"] is None


def test_into_class_reaches_the_builder_from_the_drafter_arguments(tmp_path):
    root = ta.intake_dir_of(tmp_path, OLD2)
    a = ta.args_for(append=BLOCK, into_class="NoSuchTests")
    draft, problems = drafter.draft_from_args(a, base="shop", policy=td.POLICY, intake_dir=root)
    assert any("NoSuchTests" in p for p in problems)


# ---- what the human reads --------------------------------------------------------------------------------------------------------


def test_the_draft_review_shows_an_insertion_as_new_tests_inserted_into_their_class(tmp_path):
    d = ta.draft_of(EXPECTED, must=(NODE,))
    d["contract"]["budget_profile"] = "default"
    (tmp_path / "intake").mkdir()
    root = ta.intake_dir_of(tmp_path / "intake", OLD2)
    baseline = {"target": {"must_pass": {NODE: "FAIL"}, "output_tail": "", "red_check": None}}
    text = drafter.review_text("run1", {"intake": "shop", "issue": "the issue"},
                               {"status": "DRAFTED", "draft": d, "report": {"baseline": baseline}},
                               {"usd": 0.0, "usd_complete": True, "calls": 0}, source=root)
    assert "required new tests: 1, required existing tests: 0" in text
    assert f"### `{PATH}` (inserted at the end of class AlphaTests of the existing file)" in text
    assert "The methods inserted into the class:" in text and "The code added at the end of the file:" not in text
    section = text.split("\n## New tests\n", 1)[1].split("\n## ", 1)[0]
    assert "def test_new(self):" in section and "class BetaTests" not in section and "def test_a(self)" not in section


def test_the_prompt_and_the_field_tell_the_drafter_when_to_use_into_class():
    assert "into_class" in drafter.SYSTEM and "only its methods" in drafter.SYSTEM
    desc = drafter.ChangedTest.model_fields["append"].description
    assert "with into_class, at the end of that class" in desc and "unless it goes into a class (into_class)" in desc
    assert "end of that class" in drafter.ChangedTest.model_fields["into_class"].description or "end" in drafter.ChangedTest.model_fields["into_class"].description
    assert "into_class" in drafter.SubmitDraft.model_json_schema()["$defs"]["ChangedTest"]["properties"]


# ---- the old hole in an append at the end of a file (found by Opus) ------------------------------------------------------------------------


def end_append(block, old=OLD2):
    return old.rstrip("\n") + "\n\n\n" + block.strip("\n") + "\n"


@pytest.mark.parametrize("block, name", [
    ("def f(x):\n    return x\n", "f"),                                                  # shadows the function the old tests import
    ("import os\n\n\ndef unittest():\n    pass\n", "unittest"),                          # shadows an imported module
])
def test_an_append_may_not_redefine_a_name_the_intake_imports(block, name):
    probs = ch.redefined_problems(PATH, OLD2, end_append(block))
    assert any(name in p for p in probs), probs


@pytest.mark.parametrize("block", [
    "AlphaTests.test_a = lambda self: None\n",
    "unittest.TestCase.assertEqual = lambda *a, **k: None\n",
    "import os\nos.environ['X'] = '1'\n",
    "d = {}\nd['k'] = 1\n",
    "a.b = 1\n",
    "AlphaTests.x += 1\n",
    "del AlphaTests.test_a\n",
    "(AlphaTests.p, q) = (1, 2)\n",
])
def test_an_append_may_not_assign_to_an_attribute_or_an_item_at_the_top_level(block):
    probs = ch.redefined_problems(PATH, OLD2, end_append(block))
    assert probs, block


def test_an_ordinary_append_is_still_fine_new_class_new_helper_re_import():
    block = "import unittest\nfrom lib import f\n\n\nCASES = [1, 2]\n\n\nclass N(unittest.TestCase):\n    def test_n(self):\n        self.assertEqual(f(1), 2)\n"
    assert ch.redefined_problems(PATH, OLD2, end_append(block)) == []


# ---- gaps the mutants showed -------------------------------------------------------------------------------------------------------


def test_a_content_draft_that_inserts_a_decorated_method_is_an_insertion_and_refused_for_its_decorator():
    content = EXPECTED.replace("    def test_new(self):", "    @unittest.skip('x')\n    def test_new(self):", 1)
    ins = ch.insertion(OLD2, content)
    assert ins and ins["kind"] == "class"
    assert any("decorator" in p for p in ch.insertion_problems(PATH, OLD2, ins))


def test_a_class_with_a_decorator_takes_no_inserted_tests_even_by_a_content_draft():
    old = "import unittest\n\n\n@unittest.skipIf(False, 'x')\nclass AlphaTests(unittest.TestCase):\n    def test_a(self):\n        pass\n"
    content = old + INSERTED
    ins = ch.insertion(old, content)
    assert ins and any("decorator" in p for p in ch.insertion_problems(PATH, old, ins))


def test_a_class_bound_twice_takes_no_inserted_tests_even_by_a_content_draft():
    old = OLD2.replace("\n\nif __name__", "\n\nAlphaTests = deco(AlphaTests)\n\n\nif __name__", 1)
    ins = ch.insertion(old, old.replace(AFTER_B, AFTER_B + INSERTED, 1))
    assert ins and any("exactly once" in p for p in ch.insertion_problems(PATH, old, ins))


def test_a_class_that_is_not_found_in_the_old_file_gives_a_problem_not_a_crash():
    ins = ch.insertion(OLD2, EXPECTED)
    other = OLD2.replace("class AlphaTests", "class GammaTests", 1)
    assert ch.insertion_problems(PATH, other, ins)
    assert ch.insertion_problems(PATH, "def (", ins) == []        # an old file that does not parse is another check's business


def test_the_added_region_of_an_insertion_is_limited_to_the_block_limit_plus_the_overhead_exactly():
    pad = lambda n: "".join("        # " + "x" * 60 + "\n" for _ in range(n))          # noqa: E731
    base = OLD2.replace(AFTER_B, AFTER_B + "\n    def test_new(self):\n        pass\n", 1)
    lines = (ch.MAX_BLOCK_BYTES // 71) - 1
    content = base.replace("        pass\n\n\n# a comment", pad(lines) + "        pass\n\n\n# a comment", 1)
    assert ch.insertion(OLD2, content)["kind"] == "class"
    diff = ch.insertion_bytes(OLD2, content)
    extra = ch.MAX_BLOCK_BYTES + ch.APPEND_OVERHEAD - diff
    assert extra >= 0
    exact = content.replace("        # x", "        # " + "x" * extra + "x", 1)
    over = exact.replace("        # x", "        # xx", 1)
    assert ch.insertion_bytes(OLD2, exact) == ch.MAX_BLOCK_BYTES + ch.APPEND_OVERHEAD
    assert not any("larger than" in p for p in statics_of(exact, must=()))
    assert any("larger than" in p for p in statics_of(over, must=()))


@pytest.mark.parametrize("old, block, name", [
    (OLD2.replace("from lib import f", "from lib import f as g"), "def g(x):\n    return x\n", "g"),
    (OLD2.replace("import unittest\n", "import unittest as ut\nimport unittest\n", 1), "def ut():\n    pass\n", "ut"),
    (OLD2.replace("import unittest\n", "import os.path\nimport unittest\n", 1), "def os():\n    pass\n", "os"),
])
def test_an_import_with_as_or_a_dotted_name_binds_the_name_an_append_may_not_redefine(old, block, name):
    assert any(name in p for p in ch.redefined_problems(PATH, old, end_append(block, old)))


def test_an_added_statement_that_assigns_to_a_plain_name_is_not_an_attribute_assignment():
    assert ch.redefined_problems(PATH, OLD2, end_append("x = a.b\ny: int = 1\nz = [1][0]\n")) == []


@pytest.mark.parametrize("attr", ["test_alias = test_a", "test_alias: object = test_a", "test_alias, other = test_a, test_b"])
def test_a_name_the_class_binds_by_assignment_is_taken_too(attr):
    old = OLD2.replace(AFTER_B, AFTER_B + f"\n    {attr}\n", 1)
    assert "already" in refused(old=old, block="def test_alias(self):\n    pass\n")


def test_an_augmented_assignment_in_a_class_body_names_it_too():
    old = OLD2.replace(AFTER_B, AFTER_B + "\n    test_alias = 1\n    test_alias += 1\n", 1)
    assert "already" in refused(old=old, block="def test_alias(self):\n    pass\n")


@pytest.mark.parametrize("ins", [None, {"kind": "end"}])
def test_the_class_checks_say_nothing_for_an_append_at_the_end_or_no_insertion_at_all(ins):
    assert ch.insertion_problems(PATH, OLD2, ins) == []
    assert ch.inherited_problems(PATH, ins, {f"{PATH}::AlphaTests::test_new"}) == []


@pytest.mark.parametrize("entry", [{"path": PATH, "into_class": "AlphaTests"}, {"path": PATH, "content": "x = 1\n", "into_class": "AlphaTests"}])
def test_into_class_without_append_is_refused(entry):
    out, problems = ch.from_append([entry], {PATH: OLD2}.get, intake._plain)
    assert out == [] and any("into_class goes with append" in p for p in problems)


def test_an_overridden_inherited_test_is_caught_even_when_it_is_not_the_required_node(tmp_path):
    block = "def test_inherited(self):\n    pass\n\ndef test_fresh(self):\n    self.assertEqual(1, 2)\n"
    out, problems = build(into="BetaTests", old=OLDX, block=block)
    assert problems == []
    fresh = f"{PATH}::BetaTests::test_fresh"
    d = ta.draft_of(out[0]["content"], must=(fresh,))
    before = {f"{PATH}::BetaTests::test_inherited", f"{PATH}::BetaTests::test_c"}
    got = ta.k1(tmp_path, d, OLDX, before, before | {fresh})
    assert any("override a test the class inherits" in p for p in got), got


# ---- the second review (attacker, 2026-11-14) ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("block", [
    "def test_new(self) -> locals().__setitem__('test_a', lambda self: None):\n    pass\n",       # runs when the class is built
    "def test_new(self, x: setattr(object, 'a', 1) = 1):\n    pass\n",
    "def test_new(self, *a: print(1)):\n    pass\n",
    "def test_new(self, **k: print(1)):\n    pass\n",
    "def test_new(self, *, k: print(1) = 1):\n    pass\n",
    "def test_new(self, a: int, /):\n    pass\n",
    "def test_new(self) -> None:\n    pass\n",                          # no annotations at all: nothing to evaluate
    "def test_new[T](self):\n    pass\n",
])
def test_an_inserted_method_has_no_annotations_which_run_when_the_class_is_built(block):
    assert "annotation" in refused(block=block) or "parse" in refused(block=block)


def test_the_annotation_rule_holds_for_a_content_draft_too():
    content = EXPECTED.replace("def test_new(self):", "def test_new(self) -> locals().__setitem__('test_a', None):", 1)
    ins = ch.insertion(OLD2, content)
    assert ins and any("annotation" in p for p in ch.insertion_problems(PATH, OLD2, ins))


OLD3 = OLD2.replace("\n\nclass MixinTests", "\n\ndef check(a, b):\n    assert a == b\n\n\nclass MixinTests", 1)


@pytest.mark.parametrize("block", [
    "from operator import eq as check\n",
    "import check\n",
    "if True:\n    def check(a, b):\n        pass\n",
    "try:\n    def check(a, b):\n        pass\nexcept Exception:\n    pass\n",
    "(check := lambda a, b: None)\n",
    "for check in [1]:\n    pass\n",
    "with open('x') as check:\n    pass\n",
    "try:\n    pass\nexcept Exception as check:\n    pass\n",
    "del check\n",
    "check = 1\n",
    "check += 1\n",
    "XS = [(check := i) for i in range(3)]\n",                           # a walrus in a comprehension binds in the module
    "from other import f\n",                                             # the intake imports f from lib
    "match 1:\n    case check:\n        pass\n",
])
def test_an_append_may_not_rebind_a_name_of_the_intake_by_any_statement_at_module_scope(block):
    probs = ch.redefined_problems(PATH, OLD3, end_append(block, OLD3))
    assert any("redefines" in p and ("check" in p or " f" in p) for p in probs), (block, probs)


@pytest.mark.parametrize("block", [
    "import unittest\nfrom lib import f\n",                                # the same imports again
    "XS = [check for check in range(3)]\n",                                # a comprehension has its own scope
    "g = lambda check: check\n",
    "def helper(check):\n    return check\n",                              # a parameter is local
    "def helper():\n    check = 1\n    return check\n",                       # an assignment in a function body is local
    "def helper():\n    import os as check\n    return check\n",
    "class N(unittest.TestCase):\n    check = 1\n\n    def test_n(self):\n        pass\n",     # a class body is its own scope
])
def test_an_append_that_only_uses_the_name_or_binds_it_in_another_scope_is_fine(block):
    assert ch.redefined_problems(PATH, OLD3, end_append(block, OLD3)) == []


def test_a_star_import_in_an_append_is_refused_it_rebinds_names_nobody_can_list():
    assert any("star" in p for p in ch.redefined_problems(PATH, OLD3, end_append("from os.path import *\n", OLD3)))


def test_a_name_bound_in_the_class_under_if_or_for_is_taken_too():
    old = OLD2.replace(AFTER_B, AFTER_B + "\n    if True:\n        def test_cond(self):\n            pass\n", 1)
    assert "already" in refused(old=old, block="def test_cond(self):\n    pass\n")
    old = OLD2.replace(AFTER_B, AFTER_B + "\n    for test_loop in range(2):\n        pass\n", 1)
    assert "already" in refused(old=old, block="def test_loop(self):\n    pass\n")


def test_a_name_an_inherited_attribute_of_a_base_class_of_the_file_has_is_taken_even_if_it_is_not_a_test_node():
    old = ("import unittest\n\n\nclass Base:\n    testing = False\n\n    def test_base(self):\n        pass\n\n\n"
           "class Mid(Base):\n    pass\n\n\nclass FooTests(Mid, unittest.TestCase):\n    def test_a(self):\n        pass\n")
    for name in ("testing", "test_base"):
        assert "already" in refused(into="FooTests", old=old, block=f"def {name}(self):\\n    pass\\n".replace("\\n", "\n"))
    assert build(into="FooTests", old=old, block="def test_fresh(self):\n    pass\n")[1] == []


def test_the_k3_warning_about_module_level_code_does_not_fire_for_methods_inserted_into_a_class_not_named_test():
    assert not any("module-level code" in w for w in ch.warnings(PATH, OLD2, EXPECTED, []))
    assert any("module-level code" in w for w in ch.warnings(PATH, OLD2, OLD2.replace("import unittest", "import unittest\nimport os", 1), []))
    # an insertion that also changes something else at module level is not an insertion: it still warns
    other = EXPECTED.replace("from lib import f", "from lib import f, g", 1)
    assert any("module-level code" in w for w in ch.warnings(PATH, OLD2, other, []))


@pytest.mark.parametrize("bad", ["\r", "\x0c"])
def test_a_content_draft_with_a_carriage_return_or_form_feed_in_its_insertion_is_refused(bad):
    content = EXPECTED.replace("def test_new(self):", f"def test_new(self):{bad}", 1) if bad == "\r" else EXPECTED.replace("assertEqual(f(3), 4)", f"assertEqual(f(3), 4){bad}", 1)
    assert any("carriage" in p or "form feed" in p for p in statics_of(content, must=()))


def test_bases_that_refer_to_each_other_do_not_loop():
    old = "import unittest\n\n\nclass A(B):\n    pass\n\n\nclass B(A):\n    pass\n\n\nclass C(A, unittest.TestCase):\n    def test_x(self):\n        pass\n"
    out, problems = build(into="C", old=old, block="def test_y(self):\n    pass\n")
    assert problems == [] and out
