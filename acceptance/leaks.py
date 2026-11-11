"""Old tests that will break with the new behaviour, pointed out before approve (SPEC_OLD_TEST_LEAKS).

A feature that adds a key to an output breaks every old test that expects the exact old shape. Those tests are locked
for the agent, the draft's red check cannot see them (they only break once the feature exists) and there is no reference
patch to run. So this compares the string key sets of the draft's new and changed tests with those of the old tests it
leaves alone: an old set that is a new set minus one or two words that the issue names is a likely leak. A heuristic for
Python lists, tuples, sets and dicts of strings; advice for the human, never a reason to refuse a draft.
"""
import ast
import os
import re
import stat
from pathlib import Path

from .testdetect import is_test_file
from .workspace import SPECIAL, snapshot

MIN_ELEMENTS = 4
MAX_ADDED = 2
MAX_BYTES = 1 << 20
MAX_FOUND = 20
MAX_SETS = 2000           # sets taken from one file: the comparison is bounded whatever a file holds
WORD = re.compile(r"[A-Za-z0-9_]+")


def _sets(source):
    """[(line, kind, frozenset of strings)] of the string lists/tuples/sets and string-keyed dicts of a module."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError):
        return []
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            items, kind = node.elts, "list"
        elif isinstance(node, ast.Dict):
            items, kind = node.keys, "dict"
        else:
            continue
        values = [i.value for i in items if isinstance(i, ast.Constant) and isinstance(i.value, str)]
        if len(values) >= MIN_ELEMENTS and len(values) == len(items):
            out.append((node.lineno, kind, frozenset(values)))
    return sorted(out, key=lambda t: t[0])[:MAX_SETS]


def _text(path):
    """The text of a regular file of at most MAX_BYTES, never through a symlink and never waiting on a FIFO; else None."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return None
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_BYTES:
            return None
        with os.fdopen(fd, "rb", closefd=False) as f:
            return f.read(MAX_BYTES + 1).decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    finally:
        os.close(fd)


def find(base_dir, draft, issue):
    """[{path, line, kind, added}] of the old test files (in base_dir) that the draft does not change and that look
    affected; sorted by path, at most MAX_FOUND. Advisory: whatever goes wrong, the answer is no finding, never an error
    that could stop a check, an approval or a status."""
    try:
        return _find(Path(base_dir), draft, issue)
    except Exception:           # noqa: BLE001 (MemoryError and a vanished file included: this is a hint, not a gate)
        return []


def _find(base_dir, draft, issue):
    mine = {t["path"] for t in (draft.get("new_tests") or []) + (draft.get("changed_tests") or [])}
    new_sets = [s for t in (draft.get("new_tests") or []) + (draft.get("changed_tests") or [])
                for s in _sets(t["content"])]
    words = set(WORD.findall(issue))
    found = []
    for path, digest in sorted(snapshot(base_dir, skip_cache=True).items()):
        if len(found) >= MAX_FOUND:
            break
        if digest == SPECIAL or not path.endswith(".py") or not is_test_file(path) or path in mine:
            continue
        text = _text(base_dir / path)
        if text is None:
            continue
        hit = None
        for line, kind, old in _sets(text):
            for _, _, new in new_sets:
                added = new - old
                if old < new and 1 <= len(added) <= MAX_ADDED and all(
                        WORD.fullmatch(a) and a in words for a in added):
                    hit = {"path": path, "line": line, "kind": kind, "added": sorted(added)}
                    break
            if hit:
                break
        if hit:
            found.append(hit)
    return found
