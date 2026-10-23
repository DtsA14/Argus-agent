"""W2a-ext (docs/reviews/SPEC_W2A_EXT_CHANGED_TESTS.md): a draft may give new content for existing test files
(`changed_tests`). What the harness holds deterministically, besides the W2a checks of the task baseline:

  - only test_*.py files that exist in the intake, at most MAX_FILES, protected and never writable (K5; conftest.py,
    pytest.ini, pyproject.toml and setup.cfg are never changed by a draft);
  - no old test is lost silently (K1): every node pytest collects from the intake version, in the sandbox, is still
    collected from the new one, unless `removed` names it with a reason;
  - no test function changes silently (addition 1): a test function that is in both versions and is not required is
    the same AST (line numbers aside), unless `modified` names it with a reason. Module-level code (helpers,
    fixtures, imports) may change; that is only a warning (K3);
  - no new skip or xfail (addition 2): a pytest validation that runs a changed file gets `no_skip` in the contract,
    which refuses a node of that file that ends skipped or xfail and was not marked so in the intake version
    (acceptance/validation.py). Being in the contract, it holds for the baseline, the reference run and the agent's
    acceptance alike. What counts as already skipped is read from the intake version's markers (skip, skipif and
    xfail on a function or class, or a `pytestmark`), so the contract is rebuilt the same at approval; a skip that
    happens only at run time (pytest.skip() in a test body) is not one, and such a file cannot be changed.

Whether a test got weaker cannot be checked; warnings() points the human at the places to read (K3).
"""
import ast
import difflib
import re

from . import contract as ct
from .validation import kind

MAX_FILES = 5
ENTRY_KEYS = {"path", "content", "removed", "modified"}
# A node of the file, without its path: test_x, TestC::test_x; `removed` may also name one parametrized id test_x[a]
FUNC = re.compile(r"^[A-Za-z_]\w{0,99}(::[A-Za-z_]\w{0,99})?$")
NODE = re.compile(r"^[A-Za-z_]\w{0,99}(::[A-Za-z_]\w{0,99})?(\[[^\]\s]{1,100}\])?$")
SKIP_MARKS = {"skip", "skipif", "xfail"}


def _notes(v, pattern):
    return (isinstance(v, list) and len(v) <= 50
            and all(isinstance(x, dict) and set(x) == {"node", "reason"} and isinstance(x["node"], str)
                    and pattern.match(x["node"]) and isinstance(x["reason"], str) and x["reason"].strip()
                    and len(x["reason"]) <= 500 for x in v))


def shape_problems(entries, new_paths, plain, max_bytes):
    """Problems with the shape of a draft's changed_tests, or []."""
    if not isinstance(entries, list):
        return ["changed_tests must be a list (may be empty)"]
    errors, paths = [], []
    if len(entries) > MAX_FILES:
        errors.append(f"changed_tests may change at most {MAX_FILES} files")
    for i, t in enumerate(entries):
        where = f"changed_tests[{i}]"
        if not (isinstance(t, dict) and {"path", "content"} <= set(t) <= ENTRY_KEYS and isinstance(t["content"], str)):
            errors.append(f"{where} must be {{path, content, removed?, modified?}}")
            continue
        path = t["path"]
        name = path.rsplit("/", 1)[-1] if isinstance(path, str) else ""
        if not plain(path) or not name.startswith("test_") or not name.endswith(".py"):
            errors.append(f"{where}.path must be a plain relative path to an existing test_*.py file (conftest.py, "
                          "pytest.ini, pyproject.toml and setup.cfg are never changed by a draft)")
        if len(t["content"].encode("utf-8")) > max_bytes:
            errors.append(f"{where} is larger than {max_bytes} bytes")
        nodes = []
        for k, pattern, what in (("removed", NODE, "test_x, TestC::test_x, or one parametrized id test_x[a]"),
                                 ("modified", FUNC, "test_x or TestC::test_x")):
            if not _notes(t.get(k, []), pattern):
                errors.append(f"{where}.{k} must be a list of {{node, reason}}: node is a test of the file without its "
                              f"path ({what}), reason is not empty")
            else:
                nodes += [x["node"] for x in t.get(k, [])]
        if len(set(nodes)) != len(nodes):
            errors.append(f"{where}: a node is listed twice in removed and modified")
        paths.append(path)
    if len(set(map(str, paths))) != len(paths):
        errors.append("changed_tests has duplicate paths")
    errors += [f"changed_tests: {p} is also a new test" for p in sorted(set(map(str, paths)) & set(new_paths))]
    return errors


def functions(tree):
    """{key: function node} of the tests pytest collects by default: module-level test* functions and the test*
    methods of module-level Test* classes. Key: name or Class::name."""
    out = {}
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test"):
            out[n.name] = n
        elif isinstance(n, ast.ClassDef) and n.name.startswith("Test"):
            for m in n.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and m.name.startswith("test"):
                    out[f"{n.name}::{m.name}"] = m
    return out


def func_key(node_id):
    """path::Class::test_x[a] -> Class::test_x"""
    return node_id.split("::", 1)[1].split("[", 1)[0]


def function_problems(path, old, new, required, modified):
    """Addition 1: a test function in both versions is the same AST unless it is required (its expectation changes)
    or listed in modified; a modified one exists in both versions and differs."""
    try:
        of, nf = functions(ast.parse(old)), functions(ast.parse(new))
    except (SyntaxError, ValueError) as e:
        return [f"changed test {path} does not parse (intake or new version): {e}"]
    problems = []
    for key in sorted(set(of) & set(nf) - set(required) - set(modified)):
        if ast.dump(of[key]) != ast.dump(nf[key]):
            problems.append(f"changed test {path}::{key} differs from the intake version but is neither required nor "
                            "listed in modified: restore it, or list it in modified with a reason")
    for key in sorted(modified):
        if key not in of or key not in nf:
            problems.append(f"modified {path}::{key} is not a test function in both the intake version and the new one")
        elif ast.dump(of[key]) == ast.dump(nf[key]):
            problems.append(f"modified {path}::{key} is unchanged")
    return problems


def _skip_mark(e):
    """pytest.mark.skip / skipif / xfail, called or not."""
    if isinstance(e, ast.Call):
        e = e.func
    return (isinstance(e, ast.Attribute) and e.attr in SKIP_MARKS and isinstance(e.value, ast.Attribute)
            and e.value.attr == "mark")


def _pytestmark(body):
    for s in body:
        targets = s.targets if isinstance(s, ast.Assign) else [s.target] if isinstance(s, ast.AnnAssign) else []
        if any(isinstance(t, ast.Name) and t.id == "pytestmark" for t in targets) and s.value is not None:
            items = s.value.elts if isinstance(s.value, (ast.List, ast.Tuple)) else [s.value]
            if any(_skip_mark(x) for x in items):
                return True
    return False


def skip_allowed(path, old):
    """Node id prefixes of `path` that the intake version marks skip, skipif or xfail: the whole file (a module
    pytestmark), a class (its decorator or pytestmark), or a function (its decorator). Sorted."""
    try:
        tree = ast.parse(old)
    except (SyntaxError, ValueError):
        return []
    if _pytestmark(tree.body):
        return [path]
    out = []
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test"):
            if any(_skip_mark(d) for d in n.decorator_list):
                out.append(f"{path}::{n.name}")
        elif isinstance(n, ast.ClassDef) and n.name.startswith("Test"):
            if any(_skip_mark(d) for d in n.decorator_list) or _pytestmark(n.body):
                out.append(f"{path}::{n.name}")
                continue
            out += [f"{path}::{n.name}::{m.name}" for m in n.body
                    if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and m.name.startswith("test")
                    and any(_skip_mark(d) for d in m.decorator_list)]
    return sorted(out)


def covers(spec, path):
    """The pytest validation runs at least part of `path`: a target that is the file, a node id in it, or a directory
    above it (a -k filter may select less)."""
    if kind(spec) != "pytest":
        return False
    args = spec["args"][2:]
    targets = [a for i, a in enumerate(args) if not a.startswith("-") and (i == 0 or args[i - 1] != "-k")]
    return any(t.split("::", 1)[0] == path or path.startswith(t.rstrip("/") + "/") for t in targets)


def runs_whole(spec, path):
    """The pytest validation runs every node of `path`: a target that is the file or a directory above it, no -k."""
    if kind(spec) != "pytest" or "-k" in spec["args"]:
        return False
    return any(t == path or path.startswith(t.rstrip("/") + "/") for t in spec["args"][2:])


def add_no_skip(validation, old_tests):
    """Give every pytest validation that runs a changed file its no_skip rule (in place). old_tests: {path: intake
    version text} of the changed files."""
    for v in validation:
        paths = sorted(p for p in old_tests if covers(v, p))
        if paths:
            v["no_skip"] = {"paths": paths,
                            "allowed": sorted(a for p in paths for a in skip_allowed(p, old_tests[p] or ""))}


def static_problems(draft, contract, base_files, old_tests, sha):
    """Problems with changed_tests found without running anything. old_tests: {path: intake text or None}."""
    sc, problems = contract["scope"], []
    for t in draft.get("changed_tests") or []:
        p = t["path"]
        if p not in base_files or old_tests.get(p) is None:
            problems.append(f"changed test {p} does not exist in the intake (a new file goes in new_tests)")
            continue
        if not ct.matches(p, sc["protected"]) or ct.matches(p, sc["writable"]):
            problems.append(f"changed test {p} must be protected and not writable (the agent must not be able to "
                            "edit it)")
        if sha(t["content"]) == base_files[p]:
            problems.append(f"changed test {p} is the same as in the intake")
        if not any(runs_whole(v, p) for v in contract["validation"]):
            problems.append(f"changed test {p} is not run whole by any pytest validation (a target that is the file "
                            "or a directory above it, without -k)")
        required = {func_key(n) for v in contract["validation"] for n in v.get("must_pass", [])
                    if n.split("::", 1)[0] == p}
        problems += function_problems(p, old_tests[p], t["content"],
                                      required, {m["node"] for m in t.get("modified", [])})
        for r in t.get("removed", []):
            if func_key(f"{p}::{r['node']}") in required:
                problems.append(f"removed {p}::{r['node']} is also required")
    return problems


def _covered(node_id, path, removed):
    rest = node_id[len(path) + 2:]
    return any(rest == r or ("[" not in r and rest.startswith(r + "[")) for r in removed)


def lost_problems(path, before, after, removed):
    """K1 from the two collections ({node ids}): every old node is still collected unless removed names it, and
    every removed entry names an old node that is gone."""
    problems = []
    lost = sorted(n for n in before - after if not _covered(n, path, removed))
    if lost:
        problems.append(f"changed test {path} loses {len(lost)} test(s) not listed in removed: {', '.join(lost[:20])}"
                        " (restore them, or list them in removed with a reason)")
    for r in removed:
        old = [n for n in before if _covered(n, path, [r])]
        if not old:
            problems.append(f"removed {path}::{r} is not a test of the intake version")
        elif any(n in after for n in old):
            problems.append(f"removed {path}::{r} is still collected from the new version")
    return problems


def _count(tree, pred):
    return sum(1 for n in ast.walk(tree) if pred(n))


def _weak(n):
    """A skip, an xfail or an `assert True` (K3)."""
    if isinstance(n, ast.Assert):
        return isinstance(n.test, ast.Constant) and bool(n.test.value)
    if isinstance(n, ast.Attribute):
        return n.attr in SKIP_MARKS and isinstance(n.value, ast.Attribute) and n.value.attr == "mark"
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
        return n.func.attr in ("skip", "xfail", "importorskip") and isinstance(n.func.value, ast.Name) \
            and n.func.value.id == "pytest"
    return False


def _module_rest(tree):
    """Everything at module level that is not a test function: helpers, fixtures, imports, constants, and the
    non-test parts of Test* classes."""
    out = []
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test"):
            continue
        if isinstance(n, ast.ClassDef) and n.name.startswith("Test"):
            rest = [m for m in n.body
                    if not (isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and m.name.startswith("test"))]
            out.append(f"class {n.name}: " + " ".join(ast.dump(x) for x in n.bases + n.keywords + n.decorator_list
                                                      + rest))
            continue
        out.append(ast.dump(n))
    return out


def warnings(path, old, new, removed):
    """K3: places where a changed test may have got weaker. None of them rejects a draft."""
    try:
        o, n = ast.parse(old), ast.parse(new)
    except (SyntaxError, ValueError):
        return []
    out = [f"{path}::{r['node']} is removed: {r['reason']}" for r in removed]
    of, nf = functions(o), functions(n)
    for key in sorted(set(of) & set(nf)):
        a, b = (_count(f, lambda x: isinstance(x, ast.Assert)) for f in (of[key], nf[key]))
        if b < a:
            out.append(f"{path}::{key} has fewer asserts ({a} -> {b})")
    a, b = _count(o, _weak), _count(n, _weak)
    if b > a:
        out.append(f"{path} has more skip, xfail or `assert True` ({a} -> {b})")
    if _module_rest(o) != _module_rest(n):
        out.append(f"{path} changes module-level code (helpers, fixtures, imports or class bodies): read it, it is "
                   "not held to the old version")
    return out


def unified(path, old, new, limit=400):
    """The diff from the intake version to the new one, at most `limit` lines."""
    lines = list(difflib.unified_diff(old.splitlines(), new.splitlines(), f"a/{path}", f"b/{path}", lineterm=""))
    return "\n".join(lines[:limit] + ([f"... {len(lines) - limit} more lines"] if len(lines) > limit else []))
