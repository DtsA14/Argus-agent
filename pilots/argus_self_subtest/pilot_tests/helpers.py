"""Run real unittest code in a fresh directory and return its verbose output (stderr + stdout), as the sandbox does."""
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path


def unittest_output(body):
    """Output of `python -m unittest discover -v` over one test module whose class body is `body`."""
    with tempfile.TemporaryDirectory() as d:
        pkg = Path(d) / "tests"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "test_sample.py").write_text("import unittest\n\n\nclass Sample(unittest.TestCase):\n"
                                            + textwrap.indent(textwrap.dedent(body), "    "))
        r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", ".", "-v"],
                           cwd=d, capture_output=True, text=True, timeout=60)
        return r.stderr + "\n" + r.stdout


def status_of(parsed, name):
    return parsed["tests"].get(f"tests.test_sample.Sample.{name}")
