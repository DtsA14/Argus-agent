"""How msg-style subTests print, and what a given validation.py makes of them. Run with the workspace as cwd."""
import sys

sys.path.insert(0, ".")
from acceptance.validation import parse_unittest  # noqa: E402
from pilot_tests.helpers import status_of, unittest_output  # noqa: E402

BODIES = {
    "subTest(msg) only": '''
        def test_x(self):
            with self.subTest("case a"):
                self.fail("no")
    ''',
    "subTest(msg, param)": '''
        def test_x(self):
            with self.subTest("case a", i=1):
                self.fail("no")
    ''',
    "subTest(param) only": '''
        def test_x(self):
            with self.subTest(i=1):
                self.fail("no")
    ''',
}
for name, body in BODIES.items():
    out = unittest_output(body)
    lines = [line for line in out.splitlines() if line.startswith("  test_x")]
    print(f"{name}: status {status_of(parse_unittest(out), 'test_x')!r} | {lines}")
