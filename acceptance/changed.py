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
import textwrap
import difflib
import re

from . import contract as ct
from .validation import kind

MAX_FILES = 5
ENTRY_KEYS = {"path", "content", "removed", "modified"}
# SPEC_APPEND_TESTS: an entry of the drafter's arguments may carry `append` (test code added at the end of the intake file)
# instead of `content`; from_append builds the whole file, so a draft only ever holds `content`.
MAX_BLOCK_BYTES = 50_000          # an appended block, and the content a drafter writes out whole (the added region of a pure addition)
MAX_CHANGED_BYTES = 1 << 20       # the whole content of a changed test file, in a draft (tests/test_more.py is 259 KB)
APPEND_OVERHEAD = 4               # the separator "\n\n\n" and the final "\n" are not counted against a block's limit
# A node of the file, without its path: test_x, TestC::test_x; `removed` may also name one parametrized id test_x[a]
FUNC = re.compile(r"^[A-Za-z_]\w{0,99}(::[A-Za-z_]\w{0,99})?$")
NODE = re.compile(r"^[A-Za-z_]\w{0,99}(::[A-Za-z_]\w{0,99})?(\[[^\]\s]{1,100}\])?$")
SKIP_MARKS = {"skip", "skipif", "xfail"}


def added_bytes(old, new):
    """The bytes `new` adds to `old` without its final newlines (UTF-8): what an append of a block costs."""
    return len(new.encode("utf-8")) - len(old.rstrip("\n").encode("utf-8"))


def pure_addition(old, new):
    """`new` keeps the intake text `old` (without its final newlines) as its beginning and adds something after it."""
    base = old.rstrip("\n")
    return new.startswith(base + "\n") and new[len(base):].strip() != ""


def _dump(nodes):
    return [ast.dump(n) for n in nodes]


def _class_header(c):
    return (c.name, _dump(c.bases), _dump(c.keywords), _dump(c.decorator_list), _dump(getattr(c, "type_params", [])))


def _trim(lines):
    """`lines` without its trailing empty lines (the final newlines of a file)."""
    out = list(lines)
    while out and out[-1] == "":
        out.pop()
    return out


def class_insertion(old, new):
    """SPEC_INSERT_INTO: None, or {"kind": "class", "class": name, "stmts": [the statements added], "first", "last": their
    lines in `new`, "node": the class} when `new` is `old` with statements added at the END of the body of exactly one
    top-level class and nothing else changed: the two modules have the same AST except that class's body, whose old statements
    are the beginning of the new one, and the new text is the old text plus the added lines (and one blank line before them).
    The region is found by structure, not by a text offset."""
    try:
        t_old, t_new = ast.parse(old), ast.parse(new)
    except (SyntaxError, ValueError):
        return None
    if len(t_old.body) != len(t_new.body):
        return None
    found = None
    for a, b in zip(t_old.body, t_new.body):
        if ast.dump(a) == ast.dump(b):
            continue
        if found or not (isinstance(a, ast.ClassDef) and isinstance(b, ast.ClassDef)) or _class_header(a) != _class_header(b):
            return None
        n = len(a.body)
        if len(b.body) <= n or _dump(a.body) != _dump(b.body[:n]):
            return None
        found = (b, n)
    if found is None:
        return None
    c, n = found
    stmts = c.body[n:]
    first = min(min([x.lineno] + [d.lineno for d in getattr(x, "decorator_list", [])]) for x in stmts)
    last = max(x.end_lineno for x in stmts)
    lines = new.split("\n")
    start = first - 1 if first >= 2 and lines[first - 2].strip() == "" else first          # 1-based, with one blank line before
    want, end = _trim(old.split("\n")), last
    while True:                       # comment and blank lines that trail the block's last statement belong to the block
        if _trim(lines[:start - 1] + lines[end:]) == want:
            break
        if end >= len(lines) or end - last >= 500 or not (lines[end].strip() == "" or lines[end].lstrip().startswith("#")):
            return None
        end += 1
    last = max(last, end)
    return {"kind": "class", "class": c.name, "stmts": stmts, "first": first, "last": last, "node": c}


def insertion(old, new):
    """None, {"kind": "end"} (`new` keeps `old` as its beginning and adds after it: pure_addition), or class_insertion's dict."""
    ins = class_insertion(old, new)        # first: methods added to the LAST class of a file also keep the old text as a prefix
    if ins:
        return ins
    return {"kind": "end"} if pure_addition(old, new) else None


def insertion_bytes(old, new):
    """The bytes an insertion adds: what an append costs (added_bytes), or the difference of the two texts for a class insertion."""
    ins = insertion(old, new)
    if ins and ins["kind"] == "end":
        return added_bytes(old, new)
    return len(new.encode("utf-8")) - len(old.encode("utf-8"))


def _bindings(tree, name):
    """How many times a module binds `name` anywhere (class, def, assignment, del, import, except-as, global)."""
    n = 0
    for x in ast.walk(tree):
        if isinstance(x, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and x.name == name:
            n += 1
        elif isinstance(x, ast.Name) and x.id == name and isinstance(x.ctx, (ast.Store, ast.Del)):
            n += 1
        elif isinstance(x, ast.alias) and (x.asname or x.name.split(".")[0]) == name:
            n += 1
        elif isinstance(x, ast.ExceptHandler) and x.name == name:
            n += 1
        elif isinstance(x, (ast.Global, ast.Nonlocal)) and name in x.names:
            n += 1
    return n


def _constant(node):
    return isinstance(node, ast.Constant) or (isinstance(node, ast.Tuple) and all(_constant(e) for e in node.elts))


def _class_names(c):
    """The names a class body binds directly (methods and assignments)."""
    names = set()
    for n in c.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(n.name)
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                names |= {x.id for x in ast.walk(t) if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Store)}
        elif isinstance(n, (ast.AnnAssign, ast.AugAssign)) and isinstance(n.target, ast.Name):
            names.add(n.target.id)
    return names


def insertion_problems(path, old, ins):
    """For a class insertion, whatever route made it: the class must be a top-level class bound once without decorators, and the
    added statements may only be `def test*` methods with new names, no decorators, constant defaults. A name or helper inside
    a TestCase changes how every old test of the class runs (setUp, run, an inherited or shadowed method)."""
    if not ins or ins.get("kind") != "class":
        return []
    name, where = ins["class"], f"changed test {path}"
    try:
        tree = ast.parse(old)
    except (SyntaxError, ValueError):
        return []
    tops = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name]
    if len(tops) != 1 or _bindings(tree, name) != 1:
        return [f"{where}: {name} is not a top-level class bound exactly once, tests cannot be inserted into it"]
    problems = []
    if tops[0].decorator_list:
        problems.append(f"{where}: class {name} has a decorator, which can change its methods: no tests are inserted into it")
    existing, seen = _class_names(tops[0]), set()
    for s in ins["stmts"]:
        if not isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)) or not s.name.startswith("test"):
            problems.append(f"{where}: only `def test*` methods may be inserted into class {name}, not "
                            f"{type(s).__name__} (a helper, setUp, an attribute or an import changes how the old tests run)")
            continue
        if s.decorator_list:
            problems.append(f"{where}: {name}.{s.name} has a decorator: an inserted test method takes none")
        a = s.args
        if not all(_constant(d) for d in [*a.defaults, *[k for k in a.kw_defaults if k is not None]]):
            problems.append(f"{where}: {name}.{s.name} has a default argument that is not a constant")
        if s.name in existing:
            problems.append(f"{where}: {name}.{s.name} already exists in the class (it would replace an old test)")
        if s.name in seen:
            problems.append(f"{where}: {name}.{s.name} is defined twice in the block")
        seen.add(s.name)
    return problems


def inherited_problems(path, ins, before):
    """For a class insertion: a new method whose node id the intake collection already has (before: {node ids}) overrides an
    inherited test of that class (a mixin's), which K1 would not see as a lost node."""
    if not ins or ins.get("kind") != "class":
        return []
    return [f"inserted {ins['class']}::{s.name} is already collected from the intake as {path}::{ins['class']}::{s.name}: it would "
            "override a test the class inherits" for s in ins["stmts"]
            if f"{path}::{ins['class']}::{s.name}" in before]


def _insert_into(path, old, tree, name, block, where):
    """(content, problems): `old` with the block at the end of the body of the top-level class `name`."""
    if not isinstance(name, str) or not re.match(r"^[A-Za-z_]\w{0,99}$", name):
        return None, [f"{where}: into_class must be the name of a top-level class of the file"]
    for ch_ in ("\r", "\x0b", "\x0c"):
        if ch_ in old or ch_ in block:
            return None, [f"{where}: carriage returns, vertical tabs and form feeds are not allowed in the file or the block when "
                          "inserting into a class"]
    tops = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name]
    if len(tops) != 1 or _bindings(tree, name) != 1:
        return None, [f"{where}: {name} is not a top-level class of {path} bound exactly once (not defined, defined twice, under "
                      "if/try, nested, or rebound): nothing can be inserted into it"]
    c = tops[0]
    if c.decorator_list:
        return None, [f"{where}: class {name} has a decorator: nothing is inserted into it"]
    lines, first = old.split("\n"), c.body[0]
    if first.lineno == c.lineno:
        return None, [f"{where}: class {name} has its body on the line of the class statement: nothing is inserted into it"]
    indent = lines[first.lineno - 1][:first.col_offset]
    if not indent or indent.strip(" ") != "":
        return None, [f"{where}: the body of class {name} is not indented with spaces (tabs are refused)"]
    dedented = textwrap.dedent(block).strip("\n")
    try:
        added = ast.parse(dedented)
    except (SyntaxError, ValueError) as ex:
        return None, [f"{where}: the block does not parse as methods: {ex}"]
    if not added.body:
        return None, [f"{where}: append must be a non-empty string of test code (a comment alone is not code)"]
    body = "\n".join((indent + x) if x.strip() else "" for x in dedented.split("\n"))
    content = "\n".join(lines[:c.end_lineno] + [""] + body.split("\n") + lines[c.end_lineno:])
    content = content if content.endswith("\n") else content + "\n"
    ins = class_insertion(old, content)
    if ins is None or ins["class"] != name:
        return None, [f"{where}: the block does not parse as statements at the end of class {name}"]
    if _dump(ins["stmts"]) != _dump(added.body):
        return None, [f"{where}: a string or a continuation line of the block would change its value under the class's "
                      "indentation (indent it so the string does not depend on it)"]
    bad = insertion_problems(path, old, ins)
    return (None, [p.replace(f"changed test {path}", where, 1) for p in bad]) if bad else (content, [])


def _main_guard(tree):
    """A top-level `if __name__ == "__main__":` (either order of the comparison)."""
    for n in tree.body:
        if isinstance(n, ast.If) and isinstance(n.test, ast.Compare) and len(n.test.ops) == 1 \
                and isinstance(n.test.ops[0], ast.Eq):
            sides = [n.test.left, *n.test.comparators]
            if any(isinstance(x, ast.Name) and x.id == "__name__" for x in sides) \
                    and any(isinstance(x, ast.Constant) and x.value == "__main__" for x in sides):
                return True
    return False


def from_append(entries, read, plain, limit=MAX_BLOCK_BYTES):
    """(entries, problems): the drafter's changed_tests with every `append` entry turned into a `content` entry made from
    the intake text (`read(path)` -> text or None): old.rstrip("\n") + "\n\n\n" + block.strip("\n") + "\n". None-valued
    content/append keys and empty removed/modified lists (a model dump) are dropped, so that the same file gives the same
    draft, and the same sha, by either route; entries without append are passed through; an entry with problems is
    left out of the result. The input is not changed."""
    if not isinstance(entries, list):
        return entries, []
    out, problems = [], []
    for i, e in enumerate(entries):
        if not isinstance(e, dict):
            out.append(e)
            continue
        e = {k: v for k, v in e.items()
             if not (k in ("content", "append", "into_class") and v is None) and not (k in ("removed", "modified") and v == [])}
        if "append" not in e:
            if "into_class" in e:
                problems.append(f"changed_tests[{i}]: into_class goes with append")
                continue
            out.append(e)
            continue
        where = f"changed_tests[{i}]"
        if "content" in e:
            problems.append(f"{where}: give exactly one of content or append")
            continue
        if set(e) - {"path", "append", "into_class", "removed", "modified"} or not isinstance(e.get("path"), str):
            problems.append(f"{where} must be {{path, append}} or {{path, append, into_class}} (removed and modified are for content)")
            continue
        if e.get("removed") or e.get("modified"):
            problems.append(f"{where}: removed and modified go with content; an append changes no old test")
            continue
        block, path = e["append"], e["path"]
        if not isinstance(block, str) or not block.strip():
            problems.append(f"{where}: append must be a non-empty string of test code")
            continue
        if len(block.encode("utf-8")) > limit:
            problems.append(f"{where}: append is larger than {limit} bytes")
            continue
        if not plain(path):
            problems.append(f"{where}.path must be a plain relative path to an existing test_*.py file")
            continue
        old = read(path)
        if old is None:
            problems.append(f"changed test {path} does not exist in the intake (a new file goes in new_tests)")
            continue
        try:
            tree = ast.parse(old)
        except (SyntaxError, ValueError) as ex:
            problems.append(f"changed test {path} does not parse in the intake, nothing can be appended: {ex}")
            continue
        if "into_class" in e:
            content, why = _insert_into(path, old, tree, e["into_class"], block, where)
            if why:
                problems += why
                continue
        else:
            if _main_guard(tree):
                problems.append(f"changed test {path} has an `if __name__ == \"__main__\"` block: tests appended after it "
                                "would not run when the file runs as a script, so it takes no append (use content or into_class)")
                continue
            content = old.rstrip("\n") + "\n\n\n" + block.strip("\n") + "\n"
        if len(content.encode("utf-8")) > MAX_CHANGED_BYTES:
            problems.append(f"{where}: the file with the block would be larger than {MAX_CHANGED_BYTES} bytes")
            continue
        out.append({"path": path, "content": content})
    return out, problems


def _top_names(tree):
    """The names a module binds at its top level by def, class or assignment (imports are left out: a block writes its own)."""
    names = set()
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(n.name)
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                names |= {x.id for x in ast.walk(t) if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Store)}
        elif isinstance(n, (ast.AnnAssign, ast.AugAssign)) and isinstance(n.target, ast.Name):
            names.add(n.target.id)
    return names


def _import_names(tree):
    """The names a module binds at its top level by import."""
    names = set()
    for n in tree.body:
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            names |= {(x.asname or x.name.split(".")[0]) for x in n.names}
    return names


def _attribute_targets(tree):
    """Top-level statements of `tree` that assign to or delete an attribute or an item (X.test_a = ..., d['k'] = ..., del X.a)."""
    out = []
    for n in tree.body:
        targets = n.targets if isinstance(n, (ast.Assign, ast.Delete)) else [n.target] if isinstance(n, (ast.AugAssign, ast.AnnAssign)) else []
        if any(isinstance(x, (ast.Attribute, ast.Subscript)) for t in targets for x in ast.walk(t)):
            out.append(n.lineno)
    return out


def redefined_problems(path, old, new):
    """For a pure addition: the added code must parse on its own, bind no top-level name the intake version binds (by def, class,
    assignment or IMPORT: a `def f` would shadow the `f` the old tests import) and assign to no attribute or item at the top
    level (`SomeTests.test_a = ...`, `TestCase.assertEqual = ...`, `module.f = fake` change old tests without redefining a name).
    A redefined class or function would silently replace an old test (K1 only sees a node id vanish, not a weaker body)."""
    try:
        before, added = ast.parse(old), ast.parse(new[len(old.rstrip("\n")):])
    except (SyntaxError, ValueError) as e:
        return [f"changed test {path}: the code added at its end does not parse on its own: {e}"]
    problems = []
    clash = sorted((_top_names(before) | _import_names(before)) & _top_names(added))
    if clash:
        problems.append(f"changed test {path}: the added code redefines {', '.join(clash[:10])} of the intake version, which would "
                        "replace an old test or helper (an addition keeps every old definition as it is)")
    lines = _attribute_targets(added)
    if lines:
        problems.append(f"changed test {path}: the added code assigns to or deletes an attribute or an item at its top level (added "
                        f"code line(s) {', '.join(map(str, lines[:5]))}): that can change how an old test runs; write only new tests")
    return problems


def appended_required_problems(path, before, required):
    """K1 for a pure addition: a required node must not be a test the intake version already collects (compared by its
    function, so a parametrised id counts as the test it belongs to). before: {node ids} of the intake version."""
    old = {func_key(b) for b in before if b.split("::", 1)[0] == path}
    return [f"required {n} is already a test of {path} in the intake: an appended file adds new tests (a changed "
            "expectation needs the whole file as content)"
            for n in required if n in before or func_key(n) in old]


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
        ins = insertion(old_tests[p], t["content"])
        if ins and ins["kind"] == "end":
            problems += redefined_problems(p, old_tests[p], t["content"])
        elif ins:
            problems += insertion_problems(p, old_tests[p], ins)          # SPEC_INSERT_INTO: whatever route made the draft
        if (insertion_bytes(old_tests[p], t["content"]) > MAX_BLOCK_BYTES + APPEND_OVERHEAD) if ins \
                else (len(t["content"].encode("utf-8")) > MAX_BLOCK_BYTES):
            problems.append(f"changed test {p} is larger than {MAX_BLOCK_BYTES} bytes (a file that only adds tests at its "
                            f"end may add at most that much to the intake version)")
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
    if not draft["new_tests"] and not _adds_a_test(draft, contract, old_tests):
        problems.append("a draft without new_tests needs a changed test file that only adds tests at its end and has a "
                        "required node (must_pass) that is a test the intake version does not have")
    return problems


def _defined_tests(tree):
    """{Class::test_x or test_x} defined in a module: module-level test functions and the test methods of every
    module-level class (pytest also collects a unittest.TestCase named anything, which `functions` leaves out)."""
    out = set()
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test"):
            out.add(n.name)
        elif isinstance(n, ast.ClassDef):
            out |= {f"{n.name}::{m.name}" for m in n.body
                    if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and m.name.startswith("test")}
    return out


def _adds_a_test(draft, contract, old_tests):
    """Some changed file keeps the intake text and adds after it, with a required node that is not a test function of the
    intake version (a function that is, by its AST: K1's collection makes the same demand on the node ids)."""
    for t in draft.get("changed_tests") or []:
        old = old_tests.get(t["path"])
        if old is None or not insertion(old, t["content"]):
            continue
        try:
            have = _defined_tests(ast.parse(old))
        except (SyntaxError, ValueError):
            continue
        required = {func_key(n) for v in contract["validation"] for n in v.get("must_pass", [])
                    if n.split("::", 1)[0] == t["path"]}
        if required - have:
            return True
    return False


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
        return isinstance(n.test, ast.Constant) and n.test.value is True
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
