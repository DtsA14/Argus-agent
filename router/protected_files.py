"""Which files of a patch the repository's `.argus/protected` stops (SPEC_PROTECTED_FILES P3, the gap found in the bulking-app pilot 2026-11-21).

The list is the contract for the agent: it never changes a file that matches. SPEC_PROTECTED_FILES P3 says a NEW test file of the approved draft
(`new_tests`) may match the list (`*.test.*`), because it is a new file and a human approved it; `argus apply` and the install card refused it all the
same. The rule, in one place for both: a matching file stops the patch unless it is (1) ADDED by the patch (`change == "A"`), (2) a test file by its
NAME (pytest `test_*.py` and `*_test.py`, vitest `*.test.js|jsx|ts|tsx`; never `conftest.py`, never a config), and (3) one the approved draft declared
and whose content is the content it approved (`approved_test`, from the review package, bound to the draft's hash). Everything else that matches
(a modified or deleted protected file, a new file that is not a test, a new test the draft did not declare) still stops the patch. A package that does
not say `change` and `approved_test` (an old one) stops as before.
"""
import re

from acceptance.contract import matches

TEST_NAME = re.compile(r"(^|/)(test_[^/]*\.py|[^/]*_test\.py|[^/]*\.test\.(js|jsx|ts|tsx))$")


def is_new_approved_test(f):
    """True when this entry of the package's file list is a new test file the approved draft declared."""
    p = f.get("path") if isinstance(f, dict) else None
    return isinstance(p, str) and f.get("change") == "A" and f.get("approved_test") is True and bool(TEST_NAME.search(p))


def match_of(path, globs):
    try:
        return bool(matches(path, globs))
    except Exception:
        return True                                          # a glob that cannot be read protects


def stopped(files, globs):
    """The paths of `files` (the package's [{path, change, approved_test}]) that match a protected glob and are not a new approved test."""
    return [f["path"] for f in files if isinstance(f, dict) and isinstance(f.get("path"), str) and match_of(f["path"], globs) and not is_new_approved_test(f)]


def allowed_new_tests(files, globs):
    """The paths that match a protected glob and pass because they are a new approved test (shown on the install card, never hidden)."""
    return [f["path"] for f in files if isinstance(f, dict) and isinstance(f.get("path"), str) and match_of(f["path"], globs) and is_new_approved_test(f)]
