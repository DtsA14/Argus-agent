"""SPEC_INSERT_INTO end to end, in the sandbox (the unit tests are in test_insert_into.py): a draft that only inserts a test method into an
existing unittest class, in a file with a mixin, goes through dr.check and approve; the real collection sees the new node as
path::Class::test_x and K1 refuses a method that overrides an inherited test. This is a sandbox module in conftest.py's sense (it skips
with SANDBOX NOT AVAILABLE), so it runs in a serial sandbox group of verify.sh: a test of test_acceptance_sandbox.py asserts that no
sandbox container of its own run is left, and a sandbox test outside the groups can break it."""
import copy
import hashlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_draft as tdr  # noqa: E402
from acceptance import changed as ch  # noqa: E402
from acceptance import draft as dr  # noqa: E402
from acceptance import intake  # noqa: E402
from runner import load_config  # noqa: E402
from tools import sandbox as sb  # noqa: E402


@pytest.fixture(scope="module")
def scfg():
    c = {**(load_config().get("sandbox") or {}), "kind": "docker"}
    ok, why = sb.status({**c, "environment": "argus"})
    if not ok:
        pytest.skip(f"SANDBOX NOT AVAILABLE: {why}")
    return c


CLASS_OLD = ('import unittest\n\nfrom src.shop import total\n\n\n'
             'class Mixin:\n    def test_inherited(self):\n        self.assertEqual(total([2, 3], 1), 4)\n\n\n'
             'class TotalTests(unittest.TestCase):\n    def test_total_plain(self):\n        self.assertEqual(total([2, 3], 1), 4)\n\n\n'
             'class OtherTests(Mixin, unittest.TestCase):\n    def test_other(self):\n        self.assertEqual(total([1], 0), 1)\n\n\n'
             'if __name__ == "__main__":\n    unittest.main()\n')
BLOCK = "def test_total_never_negative(self):\n    self.assertEqual(total([1], 5), 0)\n"
NODE = "tests/test_old.py::TotalTests::test_total_never_negative"
INHERITED = "tests/test_old.py::OtherTests::test_inherited"


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setattr(tdr, "OLD_TEST", CLASS_OLD)            # make_root and patch build their base from this
    tmp = tmp_path_factory.mktemp("insert_into")
    yield tdr.make_root(tmp), tmp
    mp.undo()


def built(into, block):
    out, problems = ch.from_append([{"path": "tests/test_old.py", "append": block, "into_class": into}], {"tests/test_old.py": CLASS_OLD}.get,
                                   intake._plain)
    assert problems == [], problems
    return out[0]["content"]


def draft_of(content, must):
    d = copy.deepcopy(tdr.DRAFT)
    d["new_tests"] = []
    d["contract"]["validation"] = [tdr.spec("target", "tests/test_old.py", list(must))]
    d["changed_tests"] = [{"path": "tests/test_old.py", "content": content}]
    return d


@pytest.fixture(scope="module")
def report(world, scfg):
    root, tmp = world
    d = draft_of(built("TotalTests", BLOCK), [NODE])
    return d, tdr.run_check(root, tdr.patch(tmp, {"src/shop.py": tdr.FIXED}), scfg, draft=d)


def test_a_method_inserted_into_an_existing_class_is_checked_and_approved(world, report):
    root, _ = world
    d, r = report
    r = copy.deepcopy(r)
    assert r["ok"], r["problems"]
    assert r["baseline"]["target"]["must_pass"] == {NODE: "FAIL"}                    # red by assertion, as any new test
    assert r["collection"]["tests/test_old.py"] == {"intake": 3, "new": 4, "gone": []}     # K1 on the real collection, the mixin included
    assert r["reference"]["target"] == "pass"
    rec = dr.approve(r, d, root=root)
    task = root / "fixtures" / "repos" / "fix_shop"
    content = d["changed_tests"][0]["content"]
    assert (task / "tests" / "test_old.py").read_text() == content and intake.check(rec, task) == []
    assert rec["changed"]["tests/test_old.py"]["after"] == hashlib.sha256(content.encode()).hexdigest()
    assert rec["added"] == {}
    text = content
    assert text.index("def test_total_never_negative") < text.index("class OtherTests") < text.index('if __name__ == "__main__"')


def test_the_new_method_is_the_class_s_own_and_the_old_tests_still_pass_with_it(world, report):
    d, r = report
    assert r["ok"] and r["reference"]["target"] == "pass"           # with the fix, every collected test of the file passes, old ones too
    c = d["changed_tests"][0]["content"]
    assert c.count("def test_inherited") == 1 and c.count("def test_total_plain") == 1 and c.count("def test_other") == 1


def test_a_method_that_overrides_a_test_inherited_from_a_mixin_of_the_file_is_refused_by_check(world, scfg):
    root, tmp = world
    over = CLASS_OLD.replace("        self.assertEqual(total([1], 0), 1)\n",
                             "        self.assertEqual(total([1], 0), 1)\n\n    def test_inherited(self):\n        self.assertEqual(total([1], 5), 0)\n", 1)
    assert ch.insertion(CLASS_OLD, over)["class"] == "OtherTests"            # a content draft, the builder is not involved
    d = draft_of(over, [INHERITED])
    r = tdr.run_check(root, tdr.patch(tmp, {"src/shop.py": tdr.FIXED}), scfg, draft=d)
    assert not r["ok"] and any("base class of this file" in p for p in r["problems"]), r["problems"]
