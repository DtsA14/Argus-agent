"""SPEC_APPEND_TESTS (docs/reviews/SPEC_APPEND_TESTS.md): a changed_tests entry may carry `append` (test code added at the end
of an existing test file) instead of `content`; the harness builds the whole file from the intake text. The pieces: the
pure builder (acceptance/changed.py from_append), the draft shape and size, static_problems, K1's collection, and the
drafter's arguments. Nothing here needs a sandbox: the collection is a fake."""
import copy
import hashlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_drafter as td  # noqa: E402
from acceptance import changed as ch  # noqa: E402
from acceptance import contract as ct  # noqa: E402
from acceptance import draft as dr  # noqa: E402
from acceptance import intake  # noqa: E402
from codetask import drafter  # noqa: E402

LIMIT = 50_000
MIB = 1 << 20
OLD = "import unittest\n\n\nclass T(unittest.TestCase):\n    def test_old(self):\n        pass\n"
BLOCK = "class N(unittest.TestCase):\n    def test_new(self):\n        self.assertEqual(1, 2)\n"
JOINED = OLD.rstrip("\n") + "\n\n\n" + BLOCK.strip("\n") + "\n"
PATH = "tests/test_a.py"
NEW_NODE = f"{PATH}::N::test_new"
OLD_NODE = f"{PATH}::T::test_old"


def build(entries, files=None, limit=LIMIT):
    files = {PATH: OLD} if files is None else files
    return ch.from_append(entries, files.get, intake._plain, limit)


def entry(**kw):
    return {"path": PATH, **kw}


# ---- the pure builder -------------------------------------------------------------------------------------------------

def test_the_whole_file_is_the_intake_text_then_two_blank_lines_then_the_block():
    out, problems = build([entry(append=BLOCK)])
    assert problems == []
    assert out == [{"path": PATH, "content": JOINED}]
    assert "append" not in out[0]


@pytest.mark.parametrize("old, block", [
    (OLD.rstrip("\n"), BLOCK),                         # the intake file has no final newline
    (OLD + "\n\n\n", BLOCK),                           # several final newlines
    (OLD, "\n\n" + BLOCK + "\n\n\n"),                  # blank lines around the block
    (OLD, BLOCK.rstrip("\n")),
])
def test_the_blank_lines_are_normalised(old, block):
    out, problems = build([entry(append=block)], {PATH: old})
    assert problems == [] and out[0]["content"] == JOINED


def test_an_entry_without_append_is_passed_through_and_the_input_is_never_changed():
    entries = [entry(content="x = 1\n", removed=[{"node": "test_a", "reason": "r"}]), entry(path="tests/test_b.py", append=BLOCK)]
    before = copy.deepcopy(entries)
    out, problems = build(entries, {PATH: OLD, "tests/test_b.py": OLD})
    assert entries == before
    assert problems == [] and out[0] == entries[0] and out[1]["content"] == JOINED


def test_none_valued_fields_of_a_model_dump_are_the_same_as_absent_ones():
    out, problems = build([entry(content=None, append=BLOCK, removed=[], modified=[])])
    assert problems == [] and out == [{"path": PATH, "content": JOINED}]


@pytest.mark.parametrize("e, why", [
    (entry(content=JOINED, append=BLOCK), "exactly one of content or append"),
    (entry(append=BLOCK, removed=[{"node": "test_old", "reason": "r"}]), "removed and modified"),
    (entry(append=BLOCK, modified=[{"node": "test_old", "reason": "r"}]), "removed and modified"),
    (entry(append=5), "append must be"),
    (entry(append=""), "append must be"),
    (entry(append="\n\n  \n"), "append must be"),
    (entry(append="x" * (LIMIT + 1)), "larger than"),
    (entry(path="../tests/test_a.py", append=BLOCK), "plain relative path"),
    (entry(path="tests/test_missing.py", append=BLOCK), "does not exist in the intake"),
    (entry(append=BLOCK, extra=1), "must be {path"),
])
def test_an_append_entry_that_breaks_the_form_is_refused(e, why):
    out, problems = build([e])
    assert any(why in p for p in problems), problems


def test_a_block_of_exactly_the_limit_is_accepted_and_one_more_byte_is_not():
    ok, problems = build([entry(append="#" * LIMIT)])
    assert problems == [] and ok[0]["content"].startswith(OLD.rstrip("\n"))
    assert build([entry(append="#" * (LIMIT + 1))])[1]


def test_the_block_limit_counts_bytes_not_characters():
    block = "é" * (LIMIT // 2 + 1)                      # 25,001 characters, 50,002 bytes
    assert len(block) < LIMIT and len(block.encode("utf-8")) > LIMIT
    assert any("larger than" in p for p in build([entry(append=block)])[1])


def test_a_big_intake_file_takes_a_small_block():
    big = ("x = 1\n" * 43_000)                            # about 258 KB, like tests/test_more.py
    assert len(big.encode()) > 5 * LIMIT
    out, problems = build([entry(append=BLOCK)], {PATH: big})
    assert problems == [] and out[0]["content"] == big.rstrip("\n") + "\n\n\n" + BLOCK.strip("\n") + "\n"


def test_the_whole_file_stays_under_one_mebibyte():
    old = "x = 1\n" * 170_000                             # 1,020,000 bytes: under the cap alone
    assert len(old.encode()) < MIB
    assert build([entry(append="#" * 20_000)], {PATH: old})[1] == []
    assert any("larger than" in p for p in build([entry(append="#" * 40_000)], {PATH: old})[1])


def test_the_mebibyte_cap_counts_bytes_not_characters():
    old = "# é\n" * 225_000                               # 900,000 characters, 1,125,000 bytes
    assert len(old) < MIB < len(old.encode())
    assert any("larger than" in p for p in build([entry(append=BLOCK)], {PATH: old})[1])


@pytest.mark.parametrize("main", [
    'if __name__ == "__main__":\n    unittest.main()\n',
    "if __name__ == '__main__':\n    unittest.main()\n",
    'if "__main__" == __name__:\n    unittest.main()\n',
    'if __name__ == "__main__": unittest.main()\n',
])
def test_a_file_with_a_main_guard_takes_no_append(main):
    out, problems = build([entry(append=BLOCK)], {PATH: OLD + "\n\n" + main})
    assert any("__main__" in p for p in problems), problems


@pytest.mark.parametrize("tail", [
    'def run():\n    if __name__ == "__main__":\n        pass\n',        # not at the top level
    'if __name__ == "other":\n    pass\n',
    'x = "__main__"\n',
])
def test_what_is_not_a_main_guard_is_not_refused(tail):
    out, problems = build([entry(append=BLOCK)], {PATH: OLD + "\n\n" + tail})
    assert problems == []


def test_a_file_that_does_not_parse_is_refused_before_anything_is_added():
    out, problems = build([entry(append=BLOCK)], {PATH: "def broken(:\n"})
    assert any("does not parse" in p for p in problems), problems


@pytest.mark.parametrize("old, new, expected", [
    (OLD, JOINED, True),
    (OLD.rstrip("\n"), OLD.rstrip("\n") + "\n\n" + BLOCK, True),
    (OLD, JOINED.replace("test_old", "test_older"), False),         # an old line changed
    (OLD, OLD, False),                                              # nothing added
    (OLD, OLD.rstrip("\n"), False),
    (OLD, BLOCK + OLD, False),                                      # added in front
])
def test_a_pure_addition_keeps_the_old_text_as_a_prefix_and_adds_something(old, new, expected):
    assert ch.pure_addition(old, new) is expected


# ---- the draft: shape and size ---------------------------------------------------------------------------------------

def spec(target, must, id="target"):
    return {"id": id, "executable": "python", "args": ["-m", "pytest", target], "timeout_s": 120, "min_tests": 1,
            "max_skipped": 0, "must_pass": must, "environment": "argus"}


def draft_of(content, must=(NEW_NODE,), new_tests=()):
    return {"draft_version": 1, "base": "shop",
            "plan": {"files": ["src/shop.py"], "steps": ["do it"], "risks": ["none"]},
            "contract": {"scope": {"writable": ["src/*.py"], "protected": ["tests/**", "conftest.py"]},
                         "validation": [spec(PATH, list(must))]},
            "new_tests": list(new_tests), "changed_tests": [{"path": PATH, "content": content}],
            "unverifiable": ["none"]}


def test_a_draft_without_new_tests_but_with_a_changed_test_file_has_a_valid_shape():
    assert [e for e in dr.validate_draft(draft_of(JOINED)) if "new_tests" in e] == []


@pytest.mark.parametrize("change", [
    lambda d: d.pop("changed_tests"),
    lambda d: d.update(changed_tests=[]),
    lambda d: d.update(new_tests=None),
])
def test_a_draft_that_adds_no_test_file_and_changes_none_is_still_refused(change):
    d = draft_of(JOINED)
    change(d)
    assert any("new_tests must name at least one new test file" in e for e in dr.validate_draft(d))


def test_the_draft_level_size_of_a_changed_file_is_the_mebibyte_not_the_old_fifty_thousand():
    assert not any("larger than" in e for e in dr.validate_draft(draft_of("x" * (LIMIT + 10_000))))
    assert any("larger than" in e for e in dr.validate_draft(draft_of("x" * (MIB + 1))))
    assert not any("larger than" in e for e in dr.validate_draft(draft_of("x" * MIB)))


def contract_of(d):
    return dr.build_contract(d, task="t", workspace="fixtures/repos/t", issue="i", max_usd=0.5, max_iterations=2)


def statics(d, old=OLD):
    base = {"src/shop.py": "s", "conftest.py": "c", PATH: hashlib.sha256(old.encode()).hexdigest()}
    return dr.static_problems(d, contract_of(d), base, {PATH: old})


def test_an_appended_test_with_a_required_node_needs_no_new_test_file():
    assert not any("only adds tests" in p for p in statics(draft_of(JOINED)))


@pytest.mark.parametrize("content, must", [
    (JOINED.replace("pass\n", "pass  # a changed old test\n", 1), (NEW_NODE,)),    # not a pure addition
    (JOINED, (OLD_NODE,)),                                                         # nothing required among the new tests
    (JOINED, ()),
])
def test_a_draft_without_new_tests_needs_a_pure_addition_with_a_required_node(content, must):
    assert any("only adds tests" in p for p in statics(draft_of(content, must))), "a pure addition is the only way"


def test_a_new_test_file_still_satisfies_the_old_rule():
    d = draft_of(JOINED, new_tests=[{"path": "tests/test_new.py", "content": "def test_x():\n    assert 1 == 2\n"}])
    d["contract"]["validation"].append(spec("tests/test_new.py", ["tests/test_new.py::test_x"], id="new"))
    assert not any("only adds tests" in p for p in statics(d))


def test_the_fifty_thousand_limit_holds_for_a_changed_file_that_is_not_a_pure_addition():
    changed = OLD.replace("pass", "pass  # edited") + "#" * LIMIT
    assert len(changed.encode()) > LIMIT
    assert any("larger than" in p for p in statics(draft_of(changed, must=(OLD_NODE,)), OLD))


def test_the_added_region_is_measured_from_the_intake_text_without_its_final_newlines():
    assert ch.added_bytes(OLD, JOINED) == len(("\n\n\n" + BLOCK.strip("\n") + "\n").encode())
    assert ch.added_bytes(OLD + "\n\n", JOINED) == ch.added_bytes(OLD, JOINED)
    assert ch.added_bytes("é\n", "é\n\n\nx") == 4                      # bytes of the added region, not characters


def adding(big, region):
    """`big` plus an added region of exactly `region` bytes that ends with BLOCK."""
    tail = BLOCK.strip("\n") + "\n"
    pad = region - len(("\n\n\n").encode()) - len(tail.encode()) - 1
    content = big.rstrip("\n") + "\n\n\n" + "#" * pad + "\n" + tail
    assert ch.added_bytes(big, content) == region
    return content


def test_a_changed_file_may_add_at_most_the_block_limit_plus_the_overhead_whatever_its_total():
    big = "x = 1\n" * 43_000 + OLD                                       # about 258 KB: the total is far over 50,000
    assert len(big.encode()) > 5 * LIMIT
    allowed = LIMIT + ch.APPEND_OVERHEAD
    assert not any("larger than" in p for p in statics(draft_of(adding(big, allowed)), big))
    assert any("larger than" in p for p in statics(draft_of(adding(big, allowed + 1)), big))


# ---- K1: the collection of the intake and of the new version ---------------------------------------------------------

def collected(intake_nodes, new_nodes):
    def collect(path, where, cfg, **kw):
        return (set(intake_nodes) if "intake" in str(where) else set(new_nodes)), None
    return collect


def k1(tmp_path, d, old, intake_nodes, new_nodes):
    (tmp_path / "intake" / "tests").mkdir(parents=True)
    (tmp_path / "intake" / PATH).write_text(old)
    (tmp_path / "new").mkdir()
    return dr.collection_problems(d, contract_of(d), tmp_path / "intake", tmp_path / "new", {},
                                  collect=collected(intake_nodes, new_nodes))[0]


def test_a_required_node_of_a_pure_addition_must_be_new_to_the_intake_collection(tmp_path):
    d = draft_of(JOINED)
    assert k1(tmp_path, d, OLD, {OLD_NODE}, {OLD_NODE, NEW_NODE}) == []


def test_a_required_node_the_intake_already_collects_is_refused_for_a_pure_addition(tmp_path):
    d = draft_of(JOINED, must=(OLD_NODE,))
    problems = k1(tmp_path, d, OLD, {OLD_NODE}, {OLD_NODE, NEW_NODE})
    assert any("already" in p and OLD_NODE.split("::", 1)[1] in p for p in problems), problems


def test_a_parametrised_required_node_is_compared_by_its_function(tmp_path):
    d = draft_of(JOINED, must=(f"{PATH}::T::test_old[a]",))
    problems = k1(tmp_path, d, OLD, {f"{PATH}::T::test_old[a]", f"{PATH}::T::test_old[b]"},
                  {f"{PATH}::T::test_old[a]", f"{PATH}::T::test_old[b]", NEW_NODE})
    assert any("already" in p for p in problems), problems


def test_a_changed_file_that_is_not_a_pure_addition_keeps_the_old_rule_for_required_nodes(tmp_path):
    edited = OLD.replace("pass", "assert 1 == 2") + "\n\n" + BLOCK       # an expectation changes: required, existing
    d = draft_of(edited, must=(OLD_NODE,))
    assert not any("already" in p for p in k1(tmp_path, d, OLD, {OLD_NODE}, {OLD_NODE, NEW_NODE}))


def test_k1_still_refuses_a_lost_test_for_a_pure_addition(tmp_path):
    d = draft_of(JOINED)
    problems = k1(tmp_path, d, OLD, {OLD_NODE}, {NEW_NODE})              # an appended class replaced an old one
    assert any("loses" in p for p in problems), problems


# ---- the drafter's arguments -----------------------------------------------------------------------------------------

def intake_dir_of(tmp_path, text=OLD):
    (tmp_path / "tests").mkdir(exist_ok=True)
    (tmp_path / PATH).write_text(text)
    return tmp_path


def args_for(**entry_kw):
    a = td.args_with(new_tests=[], validation=[
        {"id": "target", "paths": [PATH], "must_pass": [NEW_NODE], "min_tests": 1}])
    a["changed_tests"] = [{"path": PATH, **entry_kw}]
    return a


def test_the_drafter_turns_append_arguments_into_a_draft_with_the_whole_file(tmp_path):
    draft, problems = drafter.draft_from_args(args_for(append=BLOCK), base="shop", policy=td.POLICY,
                                              intake_dir=intake_dir_of(tmp_path))
    assert problems == [], problems
    assert draft["changed_tests"] == [{"path": PATH, "content": JOINED}]
    assert draft["new_tests"] == []


def test_a_draft_from_append_and_one_from_the_equal_content_have_the_same_sha(tmp_path):
    a, pa = drafter.draft_from_args(args_for(append=BLOCK), base="shop", policy=td.POLICY, intake_dir=intake_dir_of(tmp_path))
    b, pb = drafter.draft_from_args(args_for(content=JOINED), base="shop", policy=td.POLICY, intake_dir=intake_dir_of(tmp_path))
    assert pa == [] and pb == []
    sha = lambda d: hashlib.sha256(ct.canonical(d).encode()).hexdigest()    # noqa: E731
    assert a == b and sha(a) == sha(b)
    changed = dr.changed_record({PATH: "before"}, a)
    assert changed[PATH]["after"] == hashlib.sha256(JOINED.encode()).hexdigest()
    other, _ = drafter.draft_from_args(args_for(append=BLOCK.replace("1, 2", "1, 3")), base="shop", policy=td.POLICY,
                                       intake_dir=intake_dir_of(tmp_path))
    assert sha(other) != sha(a)


def test_model_dump_style_arguments_with_none_and_empty_fields_work(tmp_path):
    draft, problems = drafter.draft_from_args(
        args_for(content=None, append=BLOCK, removed=[], modified=[]), base="shop", policy=td.POLICY,
        intake_dir=intake_dir_of(tmp_path))
    assert problems == [] and draft["changed_tests"] == [{"path": PATH, "content": JOINED}]


def test_append_without_the_intake_is_a_problem_not_a_crash():
    draft, problems = drafter.draft_from_args(args_for(append=BLOCK), base="shop", policy=td.POLICY)
    assert draft is None and any("intake" in p for p in problems)


def test_the_append_problems_reach_the_drafter_as_problems(tmp_path):
    draft, problems = drafter.draft_from_args(args_for(append=BLOCK, content=JOINED), base="shop", policy=td.POLICY,
                                              intake_dir=intake_dir_of(tmp_path))
    assert draft is None and any("exactly one of content or append" in p for p in problems)


def test_the_old_drafts_are_built_as_before(tmp_path):
    a = td.args_with()
    draft, problems = drafter.draft_from_args(a, base="shop", policy=td.POLICY, intake_dir=intake_dir_of(tmp_path))
    assert problems == [] and draft["new_tests"] == a["new_tests"] and "changed_tests" not in draft


def test_a_draft_with_neither_new_tests_nor_changed_tests_is_still_refused(tmp_path):
    a = td.args_with(new_tests=[])
    draft, problems = drafter.draft_from_args(a, base="shop", policy=td.POLICY, intake_dir=intake_dir_of(tmp_path))
    assert any("new_tests must name at least one new test file" in p for p in problems), problems


def test_the_schema_and_the_prompt_tell_the_drafter_about_append():
    assert drafter.ChangedTest(path=PATH, append=BLOCK).append == BLOCK
    assert drafter.ChangedTest(path=PATH, content=JOINED).content == JOINED
    assert "append" in drafter.SubmitDraft.model_json_schema()["$defs"]["ChangedTest"]["properties"]
    assert "append" in drafter.SYSTEM and "new_tests" in drafter.SYSTEM


# ---- end to end, in the sandbox (skipped without an image, like tests/test_draft.py) -----------------------------------

import test_draft as tdr  # noqa: E402
from test_draft import root, scfg  # noqa: E402,F401  (fixtures)

FLOOR = "from src.shop import total\n\n\ndef test_total_floor():\n    assert total([1], 5) == 0\n"
FLOOR_NODE = "tests/test_old.py::test_total_floor"
FLOOR_FILE = tdr.OLD_TEST.rstrip("\n") + "\n\n\n" + FLOOR.strip("\n") + "\n"


def appended_draft(must=(FLOOR_NODE,)):
    d = copy.deepcopy(tdr.DRAFT)
    d["new_tests"] = []
    d["contract"]["validation"] = [tdr.spec("target", "tests/test_old.py", list(must))]
    d["changed_tests"] = [{"path": "tests/test_old.py", "content": FLOOR_FILE}]
    return d


@pytest.fixture(scope="module")
def appended_report(tmp_path_factory, scfg):
    tmp = tmp_path_factory.mktemp("appended")
    return tdr.run_check(tdr.make_root(tmp), tdr.patch(tmp, {"src/shop.py": tdr.FIXED}), scfg, draft=appended_draft())


def test_a_draft_that_only_appends_a_test_to_an_existing_file_is_checked_and_approved(root, appended_report):
    r = copy.deepcopy(appended_report)
    assert r["ok"], r["problems"]
    assert r["baseline"]["target"]["must_pass"] == {FLOOR_NODE: "FAIL"}                  # red by assertion, as any new test
    assert r["collection"]["tests/test_old.py"] == {"intake": 1, "new": 2, "gone": []}   # K1 on the real collection
    assert r["reference"]["target"] == "pass"
    rec = dr.approve(r, appended_draft(), root=root)
    task = root / "fixtures" / "repos" / "fix_shop"
    assert (task / "tests" / "test_old.py").read_text() == FLOOR_FILE and intake.check(rec, task) == []
    assert rec["changed"]["tests/test_old.py"]["after"] == hashlib.sha256(FLOOR_FILE.encode()).hexdigest()
    assert rec["added"] == {}


def test_a_required_test_the_intake_already_has_is_refused_by_k1_in_the_real_collection(root, tmp_path, scfg):
    d = appended_draft(must=("tests/test_old.py::test_total_plain",))
    d["new_tests"] = [{"path": "tests/test_new.py", "content": tdr.NEW_TEST}]         # so that only K1 can refuse it
    d["contract"]["validation"].append(tdr.spec("new", "tests/test_new.py", [tdr.NEW_NODE]))
    r = tdr.run_check(root, tdr.patch(tmp_path, {"src/shop.py": tdr.FIXED}), scfg, draft=d)
    assert not r["ok"] and any("already a test of tests/test_old.py" in p for p in r["problems"]), r["problems"]
