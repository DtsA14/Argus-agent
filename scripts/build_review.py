"""Build the review package of a DONE code-task run (M6 W3). See codetask/review.py.

  python scripts/build_review.py --run runs/<id>                    # the base commit is looked up in this checkout
  python scripts/build_review.py --run runs/<id> --repo /path/to/repo

Writes runs/<id>/review/ (changes.patch, tests.md, claims.md, provenance.json, PR.md). No model is called. The base
commit's tree is rebuilt from --repo (default: this checkout) and the contract's validations are run again in the
Docker sandbox on base commit + patch; a package whose checks fail is still written, with NOT READY at the top of
PR.md and the reasons in provenance.json. An existing package is never overwritten.
Exit codes: 0 valid package, 1 package written but not valid, 2 refused (run not DONE, package exists, ...).
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from approve_draft import sandbox_cfg  # noqa: E402
from acceptance import intake  # noqa: E402
from acceptance.validation import run_validation  # noqa: E402
from codetask import review  # noqa: E402


def main(argv=None, validate=run_validation):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", required=True, help="the run directory, e.g. runs/<id>")
    ap.add_argument("--repo", default=str(ROOT), help="the git repository that has the base commit (default: here)")
    ap.add_argument("--config")
    a = ap.parse_args(argv)
    try:
        out = review.build(a.run, repo=Path(a.repo), sandbox_cfg=sandbox_cfg(a.config), root=ROOT, validate=validate)
    except (review.ReviewError, intake.IntakeError) as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0 if out["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
