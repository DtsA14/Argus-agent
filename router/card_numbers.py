"""An example as numbers (docs/reviews/SPEC_KARTU_SETUJU.md section 4, PR 1 of T3): from the code of an example (`setup`, `run`) and its `expect`,
the table the plain-language card shows: the function called, its inputs by name with their values, the assumptions (`overrides`), and the
expected output, all read from the text of the example and nothing else.

Text is passed on as it is (bidi and control characters included): the layer that serves the card scrubs it (SPEC_KARTU_SETUJU 6).
Known limit: a name an `__init__` rebinds over a submodule of the same name is not seen.

Pure: it parses text and, to name a positional argument, reads the text of the module that defines the function through a callable the
caller gives (`source_of`; `tree_source_of` is the reader of a frozen tree). It runs nothing, it executes no text, it writes nothing, it has
no network and no model. What it shows is only what the example's own text says; the number a card shows is the number in that text.

The grammar (anything else is "not showable", which closes the card; it is never paraphrased):
- setup: only `import X [as Y]` and `from X import f [as g]` (absolute); any other statement hides what the example really sets up.
- run: one of (i) CALL followed by a chain of `.attribute` and `[constant]`, (ii) `(lambda r: {"text key": r.attribute | r[constant], ...})(CALL)`,
  (iii) `(lambda r: (r.a, r.b))(CALL)`.
- CALL: a name or a dotted name that the imports of setup resolve; every argument is a literal (numbers, text, bool, None, lists, dicts with
  text keys); no nested call, no variable, no star arguments. The display name is the resolved name, never the alias.
- A positional argument is named after the parameter of the definition found in the module's own text (a `def` without decorators, or the
  fields of a dataclass without bases, or an `__init__`); if it cannot be found it shows as `argumen N` and the card is marked defective.

Number format (fixed): the kind of the JSON value is kept (45 is not 45.0); an integer has dots for thousands (1.000.000); a fraction has a
decimal comma taken from the float's repr (0,03; 1e-05 as it is); nothing is rounded; true/false are `ya (True)` / `tidak (False)`; null is
`kosong (None)`; text is written as it is between double quotes and is never reformatted; a list or a dict has one element per line and no
commas (a comma is a decimal sign here).
"""
import ast
import json
import os
import re
import stat
import sys

from codetask import examples as ex

NOT_SHOWABLE = "contoh ini tidak bisa ditampilkan sebagai angka"
SOURCE_MAX = 512 * 1024
MODULE_PART = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
MODULE_MAX_PARTS, MODULE_MAX_CHARS = 12, 200
OPEN_DIR = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
OPEN_FILE = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_NOCTTY
NOT_REPO = frozenset(sys.stdlib_module_names) | frozenset(sys.builtin_module_names)


class _Out(Exception):
    """The example is outside the grammar: the message says where."""


# ---- number format ----------------------------------------------------------------------------------------------------

def _kind(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "text"
    if isinstance(value, list):
        return "list"
    return "object"


def _scalar(value):
    if value is None:
        return "kosong (None)"
    if isinstance(value, bool):
        return "ya (True)" if value else "tidak (False)"
    if isinstance(value, int):
        return ("-" if value < 0 else "") + f"{abs(value):,}".replace(",", ".")
    if isinstance(value, float):
        r = repr(value)
        return r.replace(".", ",")                          # also in exponent form: 1.5e-05 is shown 1,5e-05 (a dot means thousands on a card)
    return json.dumps(value, ensure_ascii=False)


def fmt(value, indent=0):
    """The text a card shows for a JSON value: its first line has no indent, the following lines are indented by `indent`."""
    pad = " " * indent
    if isinstance(value, list):
        if not value:
            return "[]"
        return "[\n" + "\n".join(f"{pad}  {fmt(v, indent + 2)}" for v in value) + f"\n{pad}]"
    if isinstance(value, dict):
        if not value:
            return "{}"
        return "{\n" + "\n".join(f"{pad}  {json.dumps(k, ensure_ascii=False)}: {fmt(v, indent + 2)}" for k, v in value.items()) + f"\n{pad}}}"
    return _scalar(value)


def _as_json(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def _json_like(value):
    """True when value is only bool, int, finite float, text, None, lists and dicts with text keys, nested at most ex.MAX_DEPTH (iterative)."""
    stack = [(value, 1)]
    while stack:
        v, d = stack.pop()
        if d > ex.MAX_DEPTH:
            return False
        if v is None or isinstance(v, (bool, int, str)):
            continue
        if isinstance(v, float):
            if v != v or v in (float("inf"), float("-inf")):
                return False
        elif isinstance(v, list):
            stack.extend((x, d + 1) for x in v)
        elif isinstance(v, dict):
            if not all(isinstance(k, str) for k in v):
                return False
            stack.extend((x, d + 1) for x in v.values())
        else:
            return False
    return True


def _entry(name, value, **more):
    return {"name": name, **more, "value_json": _as_json(value), "shown": fmt(value)}


# ---- the grammar ------------------------------------------------------------------------------------------------------

def _literal(node, what):
    try:
        value = ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError, RecursionError, MemoryError):
        raise _Out(f"{what} is not a literal") from None
    if not _json_like(value):
        raise _Out(f"{what} is not a plain number, text, bool, None, list or dict")
    return value


def _imports(setup):
    try:
        tree = ast.parse(setup)
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        raise _Out("setup is not Python") from None
    binds = {}

    def bind(name, target):
        if target.split(".")[0] in NOT_REPO:
            raise _Out("setup imports a module that is not the repository's (standard library)")
        if binds.get(name, target) != target:
            raise _Out(f"setup binds the name {name} twice")
        binds[name] = target

    for node in tree.body:
        if isinstance(node, ast.Import):
            for a in node.names:
                bind(a.asname or a.name.split(".")[0], a.name if a.asname else a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            for a in node.names:
                if a.name == "*":
                    raise _Out("setup imports with a star")
                bind(a.asname or a.name, f"{node.module}.{a.name}")
        else:
            raise _Out("setup has a statement other than an import")
    if not binds:
        raise _Out("setup imports nothing")
    return binds


def _peel(node):
    """(base, steps): the chain of `.attribute` and `[constant]` above a node, outermost last."""
    steps = []
    while isinstance(node, (ast.Attribute, ast.Subscript)):
        if isinstance(node, ast.Attribute):
            steps.append(("a", node.attr))
        else:
            key = _literal(node.slice, "an index")
            if isinstance(key, bool) or not isinstance(key, (int, str)):
                raise _Out("an index is not a number or a text")
            steps.append(("i", key))
        node = node.value
    steps.reverse()
    return node, steps


def _path(steps):
    out = ""
    for kind, v in steps:
        out += (("." if out else "") + v) if kind == "a" else f"[{json.dumps(v, ensure_ascii=False)}]"
    return out


def _projection(node, param):
    base, steps = _peel(node)
    if not (isinstance(base, ast.Name) and base.id == param and steps):
        raise _Out("a lambda reads something other than an attribute or an index of its argument")
    return _path(steps)


def _call(node, binds):
    """(resolved dotted name, [positional values], [(keyword, value)]) of a plain call of imported code."""
    if not isinstance(node, ast.Call):
        raise _Out("run does not call anything in the allowed shape")
    names = []
    f = node.func
    while isinstance(f, ast.Attribute):
        names.append(f.attr)
        f = f.value
    if not isinstance(f, ast.Name) or f.id not in binds:
        raise _Out("the function called is not one that setup imports")
    dotted = ".".join([binds[f.id], *reversed(names)])
    positional = []
    for a in node.args:
        if isinstance(a, ast.Starred):
            raise _Out("a star argument")
        positional.append(_literal(a, "an argument"))
    keywords = []
    for k in node.keywords:
        if k.arg is None:
            raise _Out("a double-star argument")
        keywords.append((k.arg, _literal(k.value, f"the argument {k.arg}")))
    return dotted, positional, keywords


def _lambda_shape(node):
    """(param, kind, parts) of `(lambda r: {...} | (...))`: kind 'dict' with [(key, path)] or 'tuple' with [path]."""
    lam = node.func
    a = lam.args
    if (len(a.args) != 1 or a.posonlyargs or a.kwonlyargs or a.vararg or a.kwarg or a.defaults or a.kw_defaults):
        raise _Out("a lambda that is not one plain argument")
    param = a.args[0].arg
    body = lam.body
    if isinstance(body, ast.Dict):
        parts = []
        for k, v in zip(body.keys, body.values):
            if not (isinstance(k, ast.Constant) and isinstance(k.value, str)):
                raise _Out("a lambda key is not a plain text")
            parts.append((k.value, _projection(v, param)))
        if len({k for k, _ in parts}) != len(parts) or not parts:
            raise _Out("a lambda with no key or a repeated key")
        return "dict", parts
    if isinstance(body, ast.Tuple) and body.elts:
        return "tuple", [_projection(v, param) for v in body.elts]
    raise _Out("a lambda that does not return a dict or a tuple of projections")


# ---- the names of positional arguments --------------------------------------------------------------------------------

def _const(keyword):
    return keyword.value.value if isinstance(keyword.value, ast.Constant) else "?"


def _decorator_kind(cls):
    """'none', 'dataclass' (one bare or literal-keyword @dataclass that keeps init and positional fields), or None (anything else)."""
    if not cls.decorator_list:
        return "none"
    if len(cls.decorator_list) != 1:
        return None
    d = cls.decorator_list[0]
    target = d.func if isinstance(d, ast.Call) else d
    if not ((isinstance(target, ast.Name) and target.id == "dataclass") or (isinstance(target, ast.Attribute) and target.attr == "dataclass")):
        return None
    for k in (d.keywords if isinstance(d, ast.Call) else []):
        if k.arg is None or not isinstance(k.value, ast.Constant):
            return None
        if (k.arg == "init" and k.value.value is not True) or (k.arg == "kw_only" and k.value.value is not False):
            return None
    return "dataclass"


def _named(node, name):
    if isinstance(node, ast.Subscript):
        node = node.value
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return re.match(rf"\s*(typing\.)?{name}\b", node.value) is not None
    return (isinstance(node, ast.Name) and node.id == name) or (isinstance(node, ast.Attribute) and node.attr == name)


def _fields(cls):
    """The positional init parameters of a dataclass body, or None when the body is not plain enough to read them in order."""
    names = []
    for stmt in cls.body:
        if isinstance(stmt, (ast.If, ast.Try, ast.For, ast.While, ast.With, ast.Match)):
            return None
        if not (isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)):
            continue
        if _named(stmt.annotation, "KW_ONLY"):
            break
        if _named(stmt.annotation, "ClassVar"):
            continue
        v = stmt.value
        if isinstance(v, ast.Call) and getattr(v.func, "id", getattr(v.func, "attr", None)) == "field":
            skip = False
            for k in v.keywords:
                if k.arg is None or (k.arg in ("init", "kw_only") and not (isinstance(k.value, ast.Constant) and isinstance(k.value.value, bool))):
                    return None
                skip = skip or (k.arg == "init" and k.value.value is False) or (k.arg == "kw_only" and k.value.value is True)
            if skip:
                continue
        names.append(stmt.target.id)
    return names


def _function_params(fn, skip_first):
    if fn.decorator_list:
        return None
    a = fn.args
    names = [x.arg for x in [*a.posonlyargs, *a.args]]
    return names[1:] if skip_first else names


def _bindings(node, name, out):
    """Every place below `node` (not inside a def or class body) that binds `name`."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if child.name == name:
                out.append(child)
            continue
        if isinstance(child, (ast.Import, ast.ImportFrom)):
            if any((a.asname or a.name.split(".")[0]) == name or a.name == "*" for a in child.names):
                out.append(child)
            continue
        if isinstance(child, ast.Name) and isinstance(child.ctx, (ast.Store, ast.Del)) and child.id == name:
            out.append(child)
        _bindings(child, name, out)
    return out


def _definition_params(text, rest):
    if not isinstance(text, str) or len(text) > SOURCE_MAX or len(rest) != 1:
        return None
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return None
    found = _bindings(tree, rest[0], [])
    if len(found) != 1 or found[0] not in tree.body:       # one binding, and a plain top-level def or class: a rebinding or a branch hides the real one
        return None
    found = found[0]
    if not isinstance(found, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return None
    if not isinstance(found, ast.ClassDef):
        return _function_params(found, False)
    kind = _decorator_kind(found)
    if kind is None or found.bases or found.keywords:
        return None
    init = [n for n in found.body if isinstance(n, ast.FunctionDef) and n.name == "__init__"]
    if len(init) > 1 or any(isinstance(n, (ast.If, ast.Try)) for n in found.body):
        return None
    if init:
        return _function_params(init[0], True)
    return _fields(found) if kind == "dataclass" else None


def _param_names(dotted, source_of):
    parts = dotted.split(".")
    for k in range(len(parts) - 1, 0, -1):
        try:
            text = source_of(".".join(parts[:k]))
        except Exception:                                   # the reader of the tree is the caller's: whatever it does, no name is found
            return None
        if text is not None:
            return _definition_params(text, parts[k:])
    return None


# ---- the derivation ---------------------------------------------------------------------------------------------------

def _refused(example, why):
    d = example if isinstance(example, dict) else {}
    return {"id": d.get("id") if isinstance(d.get("id"), str) else None, "tier": d.get("tier") if isinstance(d.get("tier"), str) else None,
            "showable": False, "why": f"{NOT_SHOWABLE}: {why}", "call": None, "inputs": [], "assumptions": [], "output": None}


def _output(expectation, kind, parts):
    """The rows of the expected output, in the order of the run."""
    def row(label, path, value):
        return {"path": path, "label": label, **{"expect_json": _as_json(value), "shown": fmt(value), "type": _kind(value)}}
    if kind is None:
        return [row(parts, parts, expectation)]
    if kind == "dict":
        if not isinstance(expectation, dict) or set(expectation) != {k for k, _ in parts}:
            raise _Out("expect does not have exactly the keys the run builds")
        return [row(k, p, expectation[k]) for k, p in parts]
    if not isinstance(expectation, list) or len(expectation) != len(parts):
        raise _Out("expect does not have exactly the elements the run builds")
    return [row(p, p, v) for p, v in zip(parts, expectation)]


def _derive(example, source_of):
    if not isinstance(example, dict):
        raise _Out("it is not an example")
    setup, run = example.get("setup"), example.get("run")
    if not isinstance(setup, str) or not isinstance(run, str) or not setup.strip() or not run.strip():
        raise _Out("setup and run must be text")
    if len(setup) > ex.SETUP_MAX or len(run) > ex.RUN_MAX:
        raise _Out("setup or run is longer than the limit of an example")
    has_expect, has_raises = "expect" in example, "raises" in example
    if has_expect == has_raises:
        raise _Out("an example has exactly one of expect and raises")
    raises = example.get("raises")
    if has_raises and not (isinstance(raises, str) and ex.RAISES.fullmatch(raises) and len(raises) <= ex.RAISES_MAX):
        raise _Out("raises is not the name of an error")
    if has_expect and not _json_like(example["expect"]):
        raise _Out("expect is not JSON")
    if not (isinstance(example.get("id"), str) and ex.ID.fullmatch(example["id"]) and example.get("tier") in ex.TIERS):
        raise _Out("id or tier is not an example's")
    overrides = {} if example.get("overrides") is None else example["overrides"]
    if not isinstance(overrides, dict) or not all(isinstance(k, str) and _json_like(v) for k, v in overrides.items()):
        raise _Out("overrides are not a map of name to JSON value")

    binds = _imports(setup)
    try:
        body = ast.parse(run, mode="eval").body
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        raise _Out("run is not one Python expression") from None
    if isinstance(body, ast.Call) and isinstance(body.func, ast.Lambda):
        if len(body.args) != 1 or body.keywords:
            raise _Out("a lambda must be applied to exactly one call")
        kind, parts = _lambda_shape(body)
        dotted, positional, keywords = _call(body.args[0], binds)
    else:
        base, steps = _peel(body)
        kind, parts = None, _path(steps)
        dotted, positional, keywords = _call(base, binds)

    names = _param_names(dotted, source_of) if positional else []
    inputs, unresolved = [], []
    for i, v in enumerate(positional):
        if names is not None and i < len(names):
            inputs.append(_entry(names[i], v, name_source="def"))
        else:
            inputs.append(_entry(f"argumen {i + 1}", v, name_source="posisi"))
            unresolved.append(f"argumen {i + 1}")
    given = {i["name"] for i in inputs}
    for k, _ in keywords:
        if k in given:
            raise _Out(f"the argument {k} is given twice")
        given.add(k)
    inputs += [_entry(k, v, name_source="nama") for k, v in keywords]
    output = ({"raises": raises, "shown": f"gagal dengan {raises}"} if has_raises else _output(example["expect"], kind, parts))
    why = (f"nama parameter tidak ditemukan di definisi fungsi untuk {', '.join(unresolved)}: kartu ini cacat, nama argumen tidak boleh ditebak"
           if unresolved else None)
    return {"id": example.get("id"), "tier": example.get("tier"), "showable": not unresolved, "why": why, "call": dotted, "inputs": inputs,
            "assumptions": [_entry(k, v) for k, v in overrides.items()], "output": output}


def derive(example, source_of):
    """The card data of one example (a parsed example: the dict of codetask.examples.parse): `{id, tier, showable, why, call, inputs,
    assumptions, output}`. `source_of(module)` gives the text of a module of the frozen tree, or None. Never raises on what a model wrote."""
    try:
        return _derive(example, source_of)
    except _Out as e:
        return _refused(example, str(e))
    except Exception as e:                                  # hostile text (deep nesting, huge numbers): the card says it cannot be shown
        return _refused(example, f"the text could not be read ({type(e).__name__})")


# ---- the frozen tree --------------------------------------------------------------------------------------------------

def _read_file(dir_fd, name):
    try:
        fd = os.open(name, OPEN_FILE, dir_fd=dir_fd)
    except OSError:
        return None
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_size > SOURCE_MAX:
            return None
        with os.fdopen(fd, "rb", closefd=False) as f:
            return f.read(SOURCE_MAX + 1).decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    finally:
        os.close(fd)


def tree_source_of(root):
    """A `source_of` for the tree at `root`: the text of module `a.b.c` (`a/b/c.py` or `a/b/c/__init__.py`), read one name at a time
    through directory descriptors and never through a symlink, never a FIFO, never past SOURCE_MAX; None for anything else."""
    def source_of(module):
        if not isinstance(module, str) or len(module) > MODULE_MAX_CHARS:
            return None
        parts = module.split(".")
        if len(parts) > MODULE_MAX_PARTS or not all(MODULE_PART.fullmatch(p) for p in parts):
            return None
        fds = []
        try:
            fds.append(os.open(root, OPEN_DIR & ~os.O_NOFOLLOW))          # the root may be a link the operator made; below it nothing is
            for p in parts[:-1]:
                fds.append(os.open(p, OPEN_DIR, dir_fd=fds[-1]))
            parent = fds[-1]
            try:                                                   # a package wins over a module of the same name, as when Python imports
                fds.append(os.open(parts[-1], OPEN_DIR, dir_fd=parent))
            except OSError:
                return _read_file(parent, parts[-1] + ".py")
            text = _read_file(fds[-1], "__init__.py")
            return text if text is not None else _read_file(parent, parts[-1] + ".py")
        except OSError:
            return None
        finally:
            for fd in fds:
                os.close(fd)
    return source_of
