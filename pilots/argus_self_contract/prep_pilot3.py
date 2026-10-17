"""Prepare pilot argus_self_3 on the VM (run from the repository root): the contract and a fake-model script that makes
the reference fix with two EditFile calls. Usage: prep_pilot3.py <pilot dir> <reference contract.py>"""
import json
import sys
from pathlib import Path

d, ref_path = Path(sys.argv[1]), Path(sys.argv[2])
WS = "fixtures/repos/argus_self_contract"
target = ["test_every_test_discovery_really_runs_is_accepted", "test_a_required_test_that_discovery_never_runs_is_rejected",
          "test_a_test_whose_file_may_not_exist_is_not_rejected", "test_a_duplicated_required_test_is_rejected",
          "test_a_name_that_cannot_be_a_unittest_test_id_is_rejected", "test_only_the_offending_tests_are_reported",
          "test_without_must_pass_nothing_changes"]
issue = ("acceptance/contract.py: validate() accepts a must_pass test that the validation's own `python -m unittest "
         "discover` options can never run, and a test listed twice in must_pass. Such a contract can never pass. "
         "Expected: validate reports every such required test in an error that names its validation (validation[i]) "
         "and the test. It must follow what unittest discovery really does with -s, -t (default: the start directory), "
         "-p (default test*.py) and -k, accept every test that discovery can run, and not reject a test only because "
         "its file might not exist (the validator does not read files). Everything else about validation stays as it "
         "is. Do not change the tests.")


def spec(i, pat, n, must=None):
    s = {"id": i, "executable": "python",
         "args": ["-m", "unittest", "discover", "-s", "pilot_tests", "-t", ".", "-p", pat],
         "timeout_s": 180, "min_tests": n, "max_skipped": 0}
    if must:
        s["must_pass"] = [f"pilot_tests.test_must_pass_reachable.MustPassReachableTest.{t}" for t in must]
    return s


c = {"contract": "argus_self_contract", "version": 1, "inputs": {"workspace": WS, "issue": issue},
     "scope": {"writable": ["acceptance/contract.py"], "protected": ["pilot_tests/**"]},
     "artifacts": [{"path": "SUMMARY.json", "type": "json", "schema": "claims_v2"}],
     "validation": [spec("unit", "test_contract_regression.py", 7), spec("target", "test_must_pass_reachable.py", 7, target)],
     "judge": [], "limits": {"max_usd": 0.5, "max_iterations": 3}, "tools": ["edit_file"]}
(d / "contract3.json").write_text(json.dumps(c, indent=2) + "\n", encoding="utf-8")

src = Path(WS, "acceptance/contract.py").read_text(encoding="utf-8")
ref = ref_path.read_text(encoding="utf-8")
HOOK = '''                errors.append(f"{where}: must_pass must be a list of dotted test ids")
'''
ANCHOR = "\n\ndef check_scope_against(c, files):"
hook_new = ref[ref.index(HOOK): ref.index(HOOK) + len(HOOK) + ref[ref.index(HOOK) + len(HOOK):].index("\n    if \"tools\" in c:")]
func = ref[ref.index("\n\ndef unreachable("): ref.index(ANCHOR)]
assert src.count(HOOK) == 1 and src.count(ANCHOR) == 1


def reply(name, args, id):
    return {"tool_calls": [{"name": name, "args": args, "id": id}], "usage": {"input_tokens": 500, "output_tokens": 60}}


claims = [{"claim": "file_changed", "path": "acceptance/contract.py"},
          {"claim": "tests_pass", "evidence": "validation:unit"},
          {"claim": "issue_fixed", "evidence": "validation:target"}]
script = [reply("ReadFile", {"path": "acceptance/contract.py"}, "r1"),
          reply("EditFile", {"path": "acceptance/contract.py", "old_text": HOOK, "new_text": hook_new}, "e1"),
          reply("EditFile", {"path": "acceptance/contract.py", "old_text": ANCHOR, "new_text": func + ANCHOR}, "e2"),
          reply("RunValidation", {"id": "target"}, "v1"),
          reply("Finish", {"claims": claims, "summary": "validate rejects required tests discovery cannot run."}, "f1")]
(d / "dry3_script.json").write_text(json.dumps(script), encoding="utf-8")
print("ok")
