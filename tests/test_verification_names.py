"""A mutant script under verification/ edits the working tree. pytest collects every test_*.py, so a mutant script named like
one was run by every full suite, in the checkout itself (found 2026-11-13: acceptance/testdetect.py left mutated)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_nothing_under_verification_is_named_like_a_test_file():
    bad = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "verification").rglob("*.py")
                 if p.name.startswith("test_") or p.name.endswith("_test.py") or p.name == "conftest.py")
    assert bad == [], f"pytest would collect (and run) these: {bad}"

