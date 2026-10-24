# Draft review: `base` (j20261024_031449_052d-d1)

Status: **DRAFTED** (a draft passed its check)

Written by the harness from the draft and its check. The draft itself was written by a model: read the tests. A passing baseline shows only that the new tests fail now, not that they test the right thing.

## Issue

```text
scripts/intake_repo.py --check NAME --repo R reports "the snapshot is not the commit's tree minus the exclusions" for
every task record (fixtures/intake/<task>.json with "kind": "task"), even when the task's repository is exactly the one
that was approved. acceptance/intake.py check_against_repo compares the workspace with the commit's tree only, but a
task's workspace is the commit's tree plus the approved tests, which the record lists:
  - record["added"]: {path: sha256 of the file} for each new test file;
  - record["changed"] (present only when existing tests were changed): {path: {"after": sha256, ...}}.

Fix check_against_repo so that, for a record whose "kind" is "task", the expected snapshot is the commit's tree minus
the exclusions, with each path of "added" set to its hash and each path of "changed" set to its "after" hash. A record
without "kind" or with "kind": "intake" is checked exactly as now.

Every other difference must still be reported, for task records too: a file changed, added or removed beyond the
approved tests, or an approved test whose content differs from its recorded hash. Executable bits are compared as now.
Nothing else changes.
```

## Plan

Files: `acceptance/intake.py`

Steps:
- In check_against_repo, keep writing the commit's tree minus record['exclude'] into a fresh directory and take its snapshot as the expected snapshot.
- When record.get('kind') == 'task', overlay on that expected snapshot each path of record.get('added') or {} with its recorded hash, and each path of record.get('changed') or {} with its 'after' hash.
- Compare the resulting expected snapshot with snapshot(workspace_dir, skip_cache=True) as before, and leave the executable-bit comparison (fresh vs workspace) as it is.

Risks:
- Applying the overlay to a record without 'kind' or with 'kind': 'intake', which must be checked exactly as now.
- Using the 'before' hash of a changed test, or the removed/modified entries, instead of its 'after' hash.
- Dropping the executable-bit comparison, which only runs when the snapshots are equal, so it stays reachable only for a task record whose approved tests match.
- Leaving the __pycache__ skip (snapshot(..., skip_cache=True)) or the exclude handling changed.
- A record that has no 'changed' key (only added tests) must not raise, and a record whose 'added' hash differs from the file must still be reported.

## Scope

Writable: `acceptance/intake.py`

Protected: `tests/**`, `fixtures/**`, `acceptance/workspace.py`, `acceptance/draft.py`, `acceptance/changed.py`, `codetask/**`, `scripts/intake_repo.py`

No scope warnings.

## Validations

- `target`: `python -m pytest tests/test_intake_task_snapshot.py`, at least 11 tests, environment `argus`; required new tests: 5, required existing tests: 0
  - new: `tests/test_intake_task_snapshot.py::test_a_task_record_whose_workspace_is_the_tree_plus_its_approved_tests_checks_clean`
  - new: `tests/test_intake_task_snapshot.py::test_a_task_record_with_changed_tests_expects_their_after_hash`
  - new: `tests/test_intake_task_snapshot.py::test_a_changed_test_that_still_has_its_before_content_is_reported`
  - new: `tests/test_intake_task_snapshot.py::test_executable_bits_are_still_compared_for_a_task_record`
  - new: `tests/test_intake_task_snapshot.py::test_a_task_record_still_reports_a_change_beyond_the_approved_tests[drop_approved]`
- `regression`: `python -m pytest tests/test_intake.py::test_only_a_plain_fixture_workspace_has_a_record`, at least 1 tests, environment `argus`; required new tests: 0, required existing tests: 1
  - existing: `tests/test_intake.py::test_only_a_plain_fixture_workspace_has_a_record`

Budget profile for the agent: `large_usd`

Tools added for the agent: `edit_file`

## New tests

### `tests/test_intake_task_snapshot.py`

On the code as it is now, validation `target`: `test_a_task_record_whose_workspace_is_the_tree_plus_its_approved_tests_checks_clean` FAIL, `test_a_task_record_with_changed_tests_expects_their_after_hash` FAIL, `test_a_changed_test_that_still_has_its_before_content_is_reported` FAIL, `test_executable_bits_are_still_compared_for_a_task_record` FAIL, `test_a_task_record_still_reports_a_change_beyond_the_approved_tests[drop_approved]` FAIL

Why they fail now (test output; check that this is the behaviour to fix):

```text
tests/test_intake_task_snapshot.py:101: in test_a_changed_test_that_still_has_its_before_content_is_reported
E   AssertionError: assert []
E    +  where [] = <function check_against_repo at 0xe6882b899ee0>({'intake_version': 1, 'kind': 'task', 'name': 'demo', 'repo': 'https://example.invalid/dem...
E    +    where <function check_against_repo at 0xe6882b899ee0> = intake.check_against_repo
tests/test_intake_task_snapshot.py:109: in test_executable_bits_are_still_compared_for_a_task_record
E   assert (["the snapshot is not the commit's tree minus the exclusions"] and False)
E    +  where False = any(<generator object test_executable_bits_are_still_compared_for_a_task_record.<locals>.<genexpr> at 0xe6882b91f850>)
========================= 5 failed, 6 passed in Xs ==========================
```

The file:

```python
"""M6 W4 task records: a task's workspace is the commit's tree minus the exclusions, plus the approved test files that
fixtures/intake/<task>.json lists in `added` ({path: sha256 of the file}) and `changed` ({path: {"after": sha256, ...}},
present only when existing tests were changed). check_against_repo must expect exactly that snapshot, and must still
report every other difference: a file changed, added or removed beyond the approved tests, an approved test whose
content differs from its hash, and the executable bits as before.

No git here: the argus sandbox has none, so intake.git is replaced by canned `ls-tree -r -z --full-tree` and
`cat-file --batch` answers, which is all write_tree runs.
"""
import hashlib

import pytest

from acceptance import intake

NEW = b"def test_new():\n    assert True\n"
OLD = b"def test_old():\n    assert 1 == 1\n"
OLD_NEW = b"def test_old():\n    assert 2 == 2\n"

# The commit's tree: path -> (bytes, executable). "verification/log.txt" is what the record excludes.
TREE = {
    "pkg/mod.py": (b"X = 1\n", False),
    "scripts/run.sh": (b"#!/bin/sh\n", True),
    "tests/test_old.py": (OLD, False),
    "verification/log.txt": (b"evidence\n", False),
}
EXCLUDE = ["verification"]
BASE = {p: f for p, f in TREE.items() if not intake.excluded(p, EXCLUDE)}


def sha(data):
    return hashlib.sha256(data).hexdigest()


class FakeGit:
    """intake.git: the commit's tree as `ls-tree -r` and `cat-file --batch` print it."""

    def __init__(self, tree):
        self.tree = tree
        self.blobs = {sha(body): body for body, _ in tree.values()}

    def __call__(self, repo, *args, data=None):
        if args[:1] == ("ls-tree",):
            rows = [f"{'100755' if ex else '100644'} blob {sha(body)}\t{path}".encode()
                    for path, (body, ex) in sorted(self.tree.items())]
            return b"\0".join(rows) + b"\0"
        if args[:1] == ("cat-file",):
            out = b""
            for line in (data or b"").decode().split():
                body = self.blobs[line]
                out += f"{line} blob {len(body)}\n".encode() + body + b"\n"
            return out
        raise AssertionError(f"unexpected git call: {args}")


@pytest.fixture
def commit(monkeypatch):
    monkeypatch.setattr(intake, "git", FakeGit(TREE))
    return TREE


def layout(root, files):
    """Write {path: (bytes, executable)} below root (which is created) and return root."""
    root.mkdir(parents=True, exist_ok=True)
    for path, (body, ex) in files.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        target.chmod(0o755 if ex else 0o644)
    return root


def record(**over):
    """A task record as approval writes it: the intake's commit and exclusions, plus the approved tests."""
    rec = {"intake_version": 1, "kind": "task", "name": "demo", "repo": "https://example.invalid/demo.git",
           "commit": "c" * 40, "tree": "d" * 40, "exclude": list(EXCLUDE), "added": {},
           "files": len(BASE), "snapshot_sha256": "0" * 64, "executable": ["scripts/run.sh"]}
    rec.update(over)
    return rec


def test_a_task_record_whose_workspace_is_the_tree_plus_its_approved_tests_checks_clean(tmp_path, commit):
    ws = layout(tmp_path / "ws", {**BASE, "tests/test_new.py": (NEW, False)})
    rec = record(added={"tests/test_new.py": sha(NEW)})
    assert intake.check_against_repo(rec, ws, "repo") == []


def test_a_task_record_with_changed_tests_expects_their_after_hash(tmp_path, commit):
    ws = layout(tmp_path / "ws", {**BASE, "tests/test_new.py": (NEW, False),
                                   "tests/test_old.py": (OLD_NEW, False)})
    rec = record(added={"tests/test_new.py": sha(NEW)},
                 changed={"tests/test_old.py": {"before": sha(OLD), "after": sha(OLD_NEW),
                                                "removed": [], "modified": []}})
    assert intake.check_against_repo(rec, ws, "repo") == []


def test_a_changed_test_that_still_has_its_before_content_is_reported(tmp_path, commit):
    ws = layout(tmp_path / "ws", BASE)                      # tests/test_old.py keeps the intake's version
    rec = record(changed={"tests/test_old.py": {"before": sha(OLD), "after": sha(OLD_NEW),
                                                "removed": [], "modified": []}})
    assert intake.check_against_repo(rec, ws, "repo")


def test_executable_bits_are_still_compared_for_a_task_record(tmp_path, commit):
    ws = layout(tmp_path / "ws", {**BASE, "tests/test_new.py": (NEW, False)})
    (ws / "pkg" / "mod.py").chmod(0o755)                   # the commit has it as 100644
    rec = record(added={"tests/test_new.py": sha(NEW)})
    problems = intake.check_against_repo(rec, ws, "repo")
    assert problems and any("executable" in p for p in problems)


def test_an_approved_test_whose_content_differs_from_its_hash_is_reported(tmp_path, commit):
    ws = layout(tmp_path / "ws", {**BASE, "tests/test_new.py": (b"def test_new():\n    assert 2 == 2\n", False)})
    rec = record(added={"tests/test_new.py": sha(NEW)})
    assert intake.check_against_repo(rec, ws, "repo")


@pytest.mark.parametrize("change", ["modify", "add", "remove", "drop_approved"])
def test_a_task_record_still_reports_a_change_beyond_the_approved_tests(tmp_path, commit, change):
    files = {**BASE, "tests/test_new.py": (NEW, False)}
    if change == "modify":
        files["pkg/mod.py"] = (b"X = 2\n", False)
    elif change == "add":
        files["pkg/extra.py"] = (b"", False)
    elif change == "remove":
        del files["tests/test_old.py"]
    else:
        del files["tests/test_new.py"]
    ws = layout(tmp_path / "ws", files)
    rec = record(added={"tests/test_new.py": sha(NEW)})
    assert intake.check_against_repo(rec, ws, "repo")


@pytest.mark.parametrize("kind", [None, "intake"])
def test_an_intake_record_is_still_checked_against_the_tree_alone(tmp_path, commit, kind):
    ws = layout(tmp_path / "ws", {**BASE, "tests/test_new.py": (NEW, False)})
    rec = record(added={"tests/test_new.py": sha(NEW)})
    rec.pop("kind")
    if kind is not None:
        rec["kind"] = kind
    assert intake.check_against_repo(rec, ws, "repo")

```

## Not verified automatically

- scripts/intake_repo.py --check NAME --repo R and its output: no test runs the CLI, which needs git and the real repository, neither of which the sandbox has
- that the records already in fixtures/intake/*.json with "kind": "task" now check clean against the Argus repository: that needs git and that repository, so it can only be confirmed by hand with scripts/intake_repo.py
- that a symlink or a special file inside a task's workspace is still reported: the snapshot comparison covers it, but no test of this file builds one (the sandbox is posix-only for that)

## Cost

Drafter: $0.0218, 15 model calls, 2 submits, 14 steps (ended: submitted).

## Approve

`approve_draft.py` checks the draft again under your task name, issue, cap and attempt limit, and publishes it only with `--approve`. Without a reference patch the task is recorded as `feasibility: unproven`; with one (`--reference-patch <patch>` instead of `--no-reference`) it is proven before the agent runs.

```bash
python scripts/approve_draft.py --draft runs/j20261024_031449_052d-d1/draft.json --task <name> --issue-file runs/j20261024_031449_052d-d1/issue.txt --max-usd <cap> --max-iterations <n> --no-reference
```
