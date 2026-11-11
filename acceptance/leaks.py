"""Old tests that will break with the new behaviour, pointed out before approve (SPEC_OLD_TEST_LEAKS).

A feature that adds a key to an output breaks every old test that expects the exact old shape. Those tests are locked
for the agent, the draft's red check cannot see them (they only break once the feature exists) and there is no reference
patch to run. So this compares the string key sets of the draft's new and changed tests with those of the old tests it
leaves alone: an old set that is a new set minus one or two words that the issue names is a likely leak. A heuristic for
Python lists, tuples, sets and dicts of strings; advice for the human, never a reason to refuse a draft.
"""
import ast
import re
from pathlib import Path

from .testdetect import is_test_file
from .workspace import snapshot

MIN_ELEMENTS = 4
MAX_ADDED = 2
MAX_BYTES = 1 << 20
MAX_FOUND = 20
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
    return out


def _text(path):
    try:
        if path.stat().st_size > MAX_BYTES:
            return None
        return path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def find(base_dir, draft, issue):
    """[{path, line, kind, added}] of the old test files (in base_dir) that the draft does not change and that look
    affected; sorted by path, at most MAX_FOUND."""
    base_dir = Path(base_dir)
    mine = {t["path"] for t in (draft.get("new_tests") or []) + (draft.get("changed_tests") or [])}
    new_sets = [s for t in (draft.get("new_tests") or []) + (draft.get("changed_tests") or [])
                for s in _sets(t["content"])]
    words = set(WORD.findall(issue or ""))
    found = []
    for path in sorted(snapshot(base_dir, skip_cache=True)):
        if len(found) >= MAX_FOUND:
            break
        if not path.endswith(".py") or not is_test_file(path) or path in mine:
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
