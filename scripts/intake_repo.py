"""Take one commit of a git repository in as a task's input repository (M6 W4).

  python scripts/intake_repo.py --repo ../some-repo --commit 3f2a1bc --name some_repo [--exclude verification ...]
  python scripts/intake_repo.py --check some_repo [--repo ../some-repo]

Writes fixtures/repos/<name> (the commit's tree, minus --exclude) and fixtures/intake/<name>.json (repo, full commit,
tree, exclusions, snapshot hash, executable files). Never overwrites. --check compares the snapshot with its record,
and with --repo also with the commit's tree rebuilt from the repository. See acceptance/intake.py.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from acceptance import intake  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", help="path of the git repository")
    ap.add_argument("--commit", help="commit to take in (any name git resolves; the record keeps the full sha)")
    ap.add_argument("--name", help="lower-case name: fixtures/repos/<name>")
    ap.add_argument("--exclude", action="append", default=[], help="a path to leave out (repeatable)")
    ap.add_argument("--check", metavar="NAME", help="check an existing intake instead")
    a = ap.parse_args(argv)
    try:
        if a.check:
            record = intake.record_for(f"fixtures/repos/{a.check}", ROOT)
            if record is None:
                print(f"no intake record for {a.check}", file=sys.stderr)
                return 2
            ws = ROOT / "fixtures" / "repos" / a.check
            problems = intake.check(record, ws) + (intake.check_against_repo(record, ws, a.repo) if a.repo else [])
            print(json.dumps({"name": a.check, "commit": record["commit"], "problems": problems}, indent=2))
            return 1 if problems else 0
        if not (a.repo and a.commit and a.name):
            ap.error("--repo, --commit and --name are required (or use --check)")
        print(json.dumps(intake.intake(a.repo, a.commit, a.name, exclude=a.exclude, root=ROOT), indent=2))
        return 0
    except intake.IntakeError as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
