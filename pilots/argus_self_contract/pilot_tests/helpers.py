"""Ground truth for the pilot: build a small test tree, run the real `python -m unittest discover` with a validation's
options, and collect the test ids it actually runs. The contract validator must agree with what discovery does."""
import copy
import re
import subprocess
import sys
import tempfile
from pathlib import Path

LINE = re.compile(r"^(\w+) \(([\w.]+)\)")


def cases(cls, methods):
    body = "".join(f"\n    def {m}(self):\n        pass\n" for m in methods)
    return f"import unittest\n\n\nclass {cls}(unittest.TestCase):{body}"


TREE = {
    "tests/__init__.py": "",
    "tests/test_a.py": cases("A", ["test_one", "test_two"]),
    "tests/test_b.py": cases("B", ["test_one"]),
    "tests/helper.py": cases("H", ["test_one"]),
    "tests/unit/__init__.py": "",
    "tests/unit/test_d.py": cases("D", ["test_one"]),
    "other/__init__.py": "",
    "other/test_c.py": cases("C", ["test_one"]),
}

# Discovery options as a validation spec writes them (after "-m unittest discover").
CONFIGS = [
    ["-s", "tests", "-t", ".", "-p", "test_a.py"],
    ["-s", "tests", "-t", "."],
    ["-s", "tests"],
    ["-s", ".", "-t", ".", "-p", "test_*.py"],
    ["-s", "tests", "-t", ".", "-p", "*.py"],
    ["-s", "tests", "-t", ".", "-k", "one"],
    ["-s", "tests", "-t", ".", "-k", "*two"],
    ["-s", "tests/unit", "-t", "."],
    ["-s", "./tests", "-t", "."],
]


def discovered(options):
    """The ids the real unittest runs with these discovery options over TREE."""
    with tempfile.TemporaryDirectory() as d:
        for rel, text in TREE.items():
            p = Path(d) / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
        r = subprocess.run([sys.executable, "-m", "unittest", "discover", *options, "-v"], cwd=d,
                           capture_output=True, text=True, timeout=60)
        ids = set()
        for line in (r.stderr + "\n" + r.stdout).splitlines():
            m = LINE.match(line)
            if m and m.group(2).rsplit(".", 1)[-1] == m.group(1):
                ids.add(m.group(2))
        return ids


def exists_under(options, test):
    """Whether TREE has the test that `test` names when module names are relative to these options' top-level
    directory (-t, default -s). Only for such tests does reachability depend on the options alone: the validator is
    static, it never reads files, so whether some other test exists is beyond what it can know."""
    import posixpath
    opts = dict(zip(options[::2], options[1::2]))
    top = posixpath.normpath(opts.get("-t", opts.get("-s", ".")))
    parts = test.split(".")
    if len(parts) < 3:
        return False
    path = posixpath.normpath(posixpath.join(top, *parts[:-2]) + ".py")
    text = TREE.get(path, "")
    return f"class {parts[-2]}(" in text and f"def {parts[-1]}(" in text


BASE = {
    "contract": "pilot_case", "version": 1,
    "inputs": {"workspace": "fixtures/repos/anything", "issue": "Fix it."},
    "scope": {"writable": ["src/**"], "protected": ["tests/**"]},
    "artifacts": [{"path": "SUMMARY.json", "type": "json", "schema": "claims_v2"}],
    "validation": [{"id": "unit", "executable": "python", "args": ["-m", "unittest", "discover", "-s", "tests"],
                    "timeout_s": 60, "min_tests": 1, "max_skipped": 0}],
    "judge": [], "limits": {"max_usd": 0.5, "max_iterations": 3},
}


def contract_with(options, must_pass):
    """A valid contract whose second validation uses these discovery options and required tests."""
    c = copy.deepcopy(BASE)
    c["validation"].append({"id": "target", "executable": "python",
                            "args": ["-m", "unittest", "discover", *options], "timeout_s": 60, "min_tests": 1,
                            "max_skipped": 0, "must_pass": list(must_pass)})
    return c
