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


def test_an_approved_new_tests_executable_bit_is_left_to_the_record_and_a_tree_files_bit_is_not(tmp_path, commit):
    # PENDING (#189 line, Atha 2026-10-30: keep it and test it): an approved new test is not in the commit's tree, so
    # its bit is not compared with the tree (intake.check compares it with the record); a tree file's bit still is
    ws = layout(tmp_path / "ws", {**BASE, "tests/test_new.py": (NEW, True)})
    rec = record(added={"tests/test_new.py": sha(NEW)})
    assert intake.check_against_repo(rec, ws, "repo") == []
    ws = layout(tmp_path / "ws2", {**BASE, "tests/test_new.py": (NEW, False), "pkg/mod.py": (b"X = 1\n", True)})
    assert intake.check_against_repo(rec, ws, "repo") == ["executable bits differ from the commit"]
