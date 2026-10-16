import unittest

from acceptance.validation import parse_unittest

from .helpers import status_of, unittest_output


class SubTestStatusTest(unittest.TestCase):
    def test_failed_subtests_make_the_test_fail(self):
        out = unittest_output('''
            def test_x(self):
                for i in range(3):
                    with self.subTest(i=i):
                        self.assertEqual(i, 0)
        ''')
        self.assertEqual(status_of(parse_unittest(out), "test_x"), "FAIL")

    def test_an_erroring_subtest_makes_the_test_error(self):
        out = unittest_output('''
            def test_x(self):
                for i in range(2):
                    with self.subTest(i=i):
                        if i == 1:
                            raise RuntimeError("boom")
        ''')
        self.assertEqual(status_of(parse_unittest(out), "test_x"), "ERROR")

    def test_a_later_failure_is_not_hidden_by_an_earlier_passing_subtest(self):
        out = unittest_output('''
            def test_x(self):
                for i in range(4):
                    with self.subTest(i=i):
                        self.assertLess(i, 3)
        ''')
        self.assertEqual(status_of(parse_unittest(out), "test_x"), "FAIL")

    def test_an_error_anywhere_among_the_subtests_wins_over_failures(self):
        for order in ("fail_then_error", "error_then_fail"):
            with self.subTest(order=order):
                first, second = ("self.fail('no')", "raise RuntimeError('boom')")
                if order == "error_then_fail":
                    first, second = second, first
                out = unittest_output(f'''
                    def test_x(self):
                        with self.subTest(i=0):
                            {first}
                        with self.subTest(i=1):
                            {second}
                ''')
                self.assertEqual(status_of(parse_unittest(out), "test_x"), "ERROR")

    def test_all_passing_subtests_are_ok(self):
        out = unittest_output('''
            def test_x(self):
                for i in range(3):
                    with self.subTest(i=i):
                        self.assertGreaterEqual(i, 0)
        ''')
        self.assertEqual(status_of(parse_unittest(out), "test_x"), "ok")

    def test_a_failing_subtest_is_never_ok_next_to_other_tests(self):
        out = unittest_output('''
            def test_a(self):
                pass

            def test_b(self):
                with self.subTest(i=0):
                    self.fail("no")

            def test_c(self):
                pass
        ''')
        parsed = parse_unittest(out)
        self.assertEqual([status_of(parsed, t) for t in ("test_a", "test_b", "test_c")], ["ok", "FAIL", "ok"])
        self.assertEqual((parsed["tests_run"], parsed["outcome"], parsed["failures"]), (3, "FAILED", 1))
