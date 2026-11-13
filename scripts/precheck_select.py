"""Which tests the pre-check (scripts/precheck.sh) runs for a change (SPEC_VERIFY_HARDENING).

  git diff --name-only <base> | python scripts/precheck_select.py     -> the test files, one per line

A fixed set that guards the verification itself (the sandbox check of no left-over container, the group list, the verify scripts),
the test modules a change touches, and the test modules named after a touched source module (`codetask/drafter.py` selects
`tests/test_drafter*.py`: a prefix of the file name, not a substring). A heuristic: a change whose tests are named otherwise is not
selected, and `verify_at` is what decides. Only files that exist are returned."""
import sys
from pathlib import Path

FIXED = ("tests/test_acceptance_sandbox.py", "tests/test_verification_names.py", "tests/test_verify_at.py",
         "tests/test_verify_provenance.py", "tests/test_xdist_groups.py")


def select(changed, existing):
    existing = set(existing)
    out = {t for t in FIXED if t in existing}
    for path in changed:
        p = Path(path)
        if p.suffix != ".py":
            continue
        if p.parts[:1] == ("tests",):
            if path in existing and p.name.startswith("test_"):
                out.add(path)
            continue
        out |= {t for t in existing if Path(t).name.startswith(f"test_{p.stem}")}
    return sorted(out)


if __name__ == "__main__":
    existing = [p.as_posix() for p in Path("tests").glob("test_*.py")]
    print("\n".join(select([ln.rstrip("\n") for ln in sys.stdin if ln.strip()], existing)))
