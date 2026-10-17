"""parse_unittest on real unittest output with subTests (pilot argus_self_2 fixed the parameter form; the message form,
subTest("case a") printed as "[case a]", is covered here). A failing subTest must never leave its test 'ok'."""
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

import pytest

from acceptance.validation import parse_unittest


def status(body):
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "tests").mkdir()
        (Path(d) / "tests" / "__init__.py").write_text("")
        (Path(d) / "tests" / "test_sample.py").write_text(
            "import unittest\n\n\nclass Sample(unittest.TestCase):\n" + textwrap.indent(textwrap.dedent(body), "    "))
        r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", ".", "-v"], cwd=d,
                           capture_output=True, text=True, timeout=60)
        return parse_unittest(r.stderr + "\n" + r.stdout)["tests"].get("tests.test_sample.Sample.test_x")


@pytest.mark.parametrize("ctx,want", [
    ('self.subTest(i=1)', "FAIL"),
    ('self.subTest("case a")', "FAIL"),
    ('self.subTest("case a", i=1)', "FAIL"),
    ('self.subTest("a (b) ... c [d]")', "FAIL"),             # the message itself looks like the syntax
    ('self.subTest(msg="m", i="x ... y")', "FAIL"),
])
def test_a_failing_subtest_in_every_printed_form_makes_the_test_fail(ctx, want):
    assert status(f'''
        def test_x(self):
            with {ctx}:
                self.fail("no")
    ''') == want


def test_an_erroring_message_subtest_wins_over_a_failing_one():
    assert status('''
        def test_x(self):
            with self.subTest("first"):
                self.fail("no")
            with self.subTest("second"):
                raise RuntimeError("boom")
    ''') == "ERROR"


def test_passing_message_subtests_leave_the_test_ok():
    assert status('''
        def test_x(self):
            for name in ("a", "b"):
                with self.subTest(name):
                    pass
    ''') == "ok"
