import unittest

from acceptance.contract import validate

from .helpers import CONFIGS, contract_with, discovered, exists_under


class MustPassReachableTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.found = {tuple(o): discovered(o) for o in CONFIGS}
        cls.all = set().union(*cls.found.values())

    def test_every_test_discovery_really_runs_is_accepted(self):
        for options, ids in self.found.items():
            with self.subTest(options=options):
                self.assertTrue(ids)
                self.assertEqual(validate(contract_with(options, sorted(ids))), [])

    def test_a_required_test_that_discovery_never_runs_is_rejected(self):
        # Every id some configuration runs, checked under every other configuration where the test it names exists:
        # discovery does not run it there, so the options make it unreachable and the contract can be rejected.
        checked = 0
        for options, ids in self.found.items():
            for test in sorted(t for t in self.all - ids if exists_under(list(options), t)):
                checked += 1
                with self.subTest(options=options, test=test):
                    errors = validate(contract_with(options, [test]))
                    self.assertTrue(any(test in e and "validation[1]" in e for e in errors), errors)
        self.assertGreater(checked, 20)                      # the ground truth really covers the options (23)

    def test_a_test_whose_file_may_not_exist_is_not_rejected(self):
        # The validator never reads files: a required test it cannot rule out from the options alone is accepted (a
        # missing test still fails acceptance at run time, where its validation reports it did not run).
        for options, test in ((["-s", "tests", "-t", "."], "tests.test_zz.Z.test_one"),
                              (["-s", "tests"], "tests.test_a.A.test_one"),
                              (["-s", ".", "-t", ".", "-p", "test_*.py"], "test_a.A.test_one")):
            with self.subTest(options=options, test=test):
                self.assertEqual(validate(contract_with(options, [test])), [])

    def test_a_duplicated_required_test_is_rejected(self):
        errors = validate(contract_with(["-s", "tests", "-t", "."], ["tests.test_a.A.test_one"] * 2))
        self.assertTrue(any("validation[1]" in e and "tests.test_a.A.test_one" in e for e in errors), errors)

    def test_a_name_that_cannot_be_a_unittest_test_id_is_rejected(self):
        for test in ("test_a.test_one", "tests.test_a"):
            with self.subTest(test=test):
                errors = validate(contract_with(["-s", "tests", "-t", "."], [test]))
                self.assertTrue(any(test in e for e in errors), errors)

    def test_only_the_offending_tests_are_reported(self):
        errors = validate(contract_with(["-s", "tests", "-t", ".", "-p", "test_a.py"],
                                        ["tests.test_a.A.test_one", "tests.test_b.B.test_one"]))
        must = [e for e in errors if "must_pass" in e or "tests.test_" in e]
        self.assertTrue(must and all("tests.test_b.B.test_one" in e for e in must), errors)

    def test_without_must_pass_nothing_changes(self):
        self.assertEqual(validate(contract_with(["-s", "tests", "-t", ".", "-p", "test_a.py"], [])), [])
