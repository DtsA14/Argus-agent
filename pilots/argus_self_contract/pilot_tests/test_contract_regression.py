import copy
import json
import unittest
from pathlib import Path

from acceptance.contract import validate

from .helpers import BASE, contract_with

ROOT = Path(__file__).resolve().parent.parent


class ContractRegressionTest(unittest.TestCase):
    """What contract validation already gets right must stay right."""

    def test_every_contract_in_the_repository_stays_valid(self):
        paths = sorted(ROOT.glob("fixtures/contracts/*.json"))
        self.assertGreater(len(paths), 10)
        for p in paths:
            with self.subTest(contract=p.name):
                self.assertEqual(validate(json.loads(p.read_text(encoding="utf-8"))), [])

    def test_the_base_contract_is_valid(self):
        self.assertEqual(validate(copy.deepcopy(BASE)), [])

    def test_unknown_and_missing_keys(self):
        c = copy.deepcopy(BASE)
        c["extra"] = 1
        del c["judge"]
        errors = validate(c)
        self.assertTrue(any("unknown key 'extra'" in e for e in errors) and any("missing key 'judge'" in e for e in errors))

    def test_command_rules(self):
        for args, why in ((["-m", "pytest"], "must start with"), (["-m", "unittest", "discover", "-x", "y"], "not allowed"),
                          (["-m", "unittest", "discover", "-s"], "exactly one value")):
            with self.subTest(args=args):
                c = copy.deepcopy(BASE)
                c["validation"][0]["args"] = args
                self.assertTrue(any(why in e for e in validate(c)), validate(c))

    def test_numeric_limits(self):
        for key, value in (("timeout_s", 0), ("min_tests", 0), ("max_skipped", -1)):
            with self.subTest(key=key):
                c = copy.deepcopy(BASE)
                c["validation"][0][key] = value
                self.assertTrue(any(key in e for e in validate(c)), validate(c))

    def test_duplicate_validation_ids_and_malformed_must_pass(self):
        c = contract_with(["-s", "tests", "-t", "."], ["not a dotted id"])
        c["validation"][1]["id"] = "unit"
        errors = validate(c)
        self.assertTrue(any("duplicate id 'unit'" in e for e in errors), errors)
        self.assertTrue(any("must_pass must be a list of dotted test ids" in e for e in errors), errors)

    def test_tools_and_limits(self):
        c = copy.deepcopy(BASE)
        c["tools"] = ["run_shell"]
        c["limits"]["max_usd"] = 9
        errors = validate(c)
        self.assertTrue(any("cannot be granted" in e for e in errors) and any("max_usd" in e for e in errors), errors)
