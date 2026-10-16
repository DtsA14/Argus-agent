import unittest

from acceptance.validation import parse_unittest

from .helpers import status_of, unittest_output


class ParserRegressionTest(unittest.TestCase):
    """What the parser already gets right must stay right."""

    def test_plain_statuses_and_summary(self):
        out = unittest_output('''
            def test_ok(self):
                pass

            def test_fail(self):
                self.assertEqual(1, 2)

            def test_error(self):
                raise RuntimeError("boom")

            @unittest.skip("not today")
            def test_skip(self):
                pass
        ''')
        parsed = parse_unittest(out)
        self.assertEqual([status_of(parsed, t) for t in ("test_ok", "test_fail", "test_error")], ["ok", "FAIL", "ERROR"])
        self.assertTrue(status_of(parsed, "test_skip").startswith("skipped"))
        self.assertEqual((parsed["tests_run"], parsed["outcome"], parsed["failures"], parsed["errors"],
                          parsed["skipped"]), (4, "FAILED", 1, 1, 1))

    def test_a_docstring_line_comes_before_the_status(self):
        out = unittest_output('''
            def test_doc(self):
                """A docstring that unittest prints before the status."""
                pass
        ''')
        parsed = parse_unittest(out)
        self.assertEqual(status_of(parsed, "test_doc"), "ok")
        self.assertEqual((parsed["tests_run"], parsed["outcome"]), (1, "OK"))

    def test_an_all_passing_run(self):
        out = unittest_output('''
            def test_a(self):
                pass

            def test_b(self):
                pass
        ''')
        parsed = parse_unittest(out)
        self.assertEqual((parsed["tests_run"], parsed["outcome"], parsed["failures"], parsed["errors"]), (2, "OK", 0, 0))

    def test_no_tests(self):
        parsed = parse_unittest("\n----------------------------------------------------------------------\n"
                                "Ran 0 tests in 0.000s\n\nNO TESTS RAN\n")
        self.assertEqual((parsed["tests_run"], parsed["outcome"]), (0, "NO TESTS RAN"))

    def test_missing_pieces_stay_none(self):
        parsed = parse_unittest("garbage without a summary")
        self.assertEqual((parsed["tests_run"], parsed["outcome"], parsed["tests"]), (None, None, {}))
