"""Mutants for INSERT-INTO (acceptance/changed.py, acceptance/draft.py, codetask/drafter.py; SPEC_INSERT_INTO): each applied alone in a worktree,
tests/test_insert_into.py and tests/test_append_tests.py run with -x; killed = a test FAILED and pytest reported no error.
Usage: <this> <worktree> <python>   (--check: only count the patterns; --only <text>: only the mutants whose name has the text)"""
import os
import subprocess
import sys
from pathlib import Path

C, D, R = "acceptance/changed.py", "acceptance/draft.py", "codetask/drafter.py"
T = ["-rfEs", "tests/test_insert_into.py", "tests/test_append_tests.py"]
M = [
    # the structural predicate
    ("a text prefix is tried before the class structure", [(C, "    ins = class_insertion(old, new)        # first: methods added to the LAST class of a file also keep the old text as a prefix\n    if ins:\n        return ins\n    return {\"kind\": \"end\"} if pure_addition(old, new) else None",
                                                           "    return {\"kind\": \"end\"} if pure_addition(old, new) else class_insertion(old, new)")]),
    ("a module that gained a statement may be an insertion", [(C, "    if len(t_old.body) != len(t_new.body):\n        return None\n    found = None", "    found = None")]),
    ("two classes may change", [(C, "        if found or not (isinstance(a, ast.ClassDef)", "        if not (isinstance(a, ast.ClassDef)")]),
    ("the class header may change", [(C, "_class_header(a) != _class_header(b):\n            return None", "False:\n            return None")]),
    ("the old statements of the class may change", [(C, "_dump(a.body) != _dump(b.body[:n]):", "False:")]),
    ("a class that only lost statements counts", [(C, "if len(b.body) <= n or _dump", "if len(b.body) < n or _dump")]),
    ("a decorator line is not part of the region", [(C, "first = min(min([x.lineno] + [d.lineno for d in getattr(x, \"decorator_list\", [])]) for x in stmts)", "first = min(x.lineno for x in stmts)")]),
    ("no blank line is taken before the region", [(C, "start = first - 1 if first >= 2 and lines[first - 2].strip() == \"\" else first", "start = first")]),
    ("the text need not be the old text plus the lines", [(C, "        if _trim(lines[:start - 1] + lines[end:]) == want:\n            break", "        if True:\n            break")]),
    ("trailing comment lines of the block are not followed", [(C, "if end >= len(lines) or end - last >= 500 or not (lines[end].strip() == \"\" or lines[end].lstrip().startswith(\"#\")):", "if True:")]),
    ("any trailing line belongs to the block", [(C, "or not (lines[end].strip() == \"\" or lines[end].lstrip().startswith(\"#\")):", "or False:")]),
    ("an insertion is measured like an append", [(C, "    if ins and ins[\"kind\"] == \"end\":\n        return added_bytes(old, new)", "    if True:\n        return added_bytes(old, new)")]),
    ("the size rule measures an insertion like an append", [(C, "(insertion_bytes(old_tests[p], t[\"content\"]) > MAX_BLOCK_BYTES + APPEND_OVERHEAD) if ins", "(added_bytes(old_tests[p], t[\"content\"]) > MAX_BLOCK_BYTES + APPEND_OVERHEAD) if ins")]),
    # the whitelist
    ("a class bound twice takes inserted tests", [(C, "    if len(tops) != 1 or _bindings(tree, name) != 1:\n        return [f\"{where}", "    if len(tops) != 1:\n        return [f\"{where}")]),
    ("a decorated class takes inserted tests", [(C, "    if tops[0].decorator_list:\n        problems.append", "    if False:\n        problems.append")]),
    ("a name that is not a test is allowed", [(C, "or not s.name.startswith(\"test\"):\n            problems.append(f\"{where}: only", "or False:\n            problems.append(f\"{where}: only")]),
    ("only plain def is a method", [(C, "if not isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)) or not s.name", "if not isinstance(s, ast.FunctionDef) or not s.name")]),
    ("a decorated method is allowed", [(C, "        if s.decorator_list:\n            problems.append(f\"{where}: {name}.{s.name} has a decorator", "        if False:\n            problems.append(f\"{where}: {name}.{s.name} has a decorator")]),
    ("any default argument is allowed", [(C, "if not all(_constant(d) for d in [*a.defaults, *[k for k in a.kw_defaults if k is not None]]):", "if False:")]),
    ("a keyword-only default is not looked at", [(C, "[*a.defaults, *[k for k in a.kw_defaults if k is not None]]", "[*a.defaults]")]),
    ("a tuple is not a constant", [(C, "isinstance(node, ast.Constant) or (isinstance(node, ast.Tuple) and all(_constant(e) for e in node.elts))", "isinstance(node, ast.Constant)")]),
    ("an existing name may be replaced", [(C, "        if s.name in existing:\n            problems.append", "        if False:\n            problems.append")]),
    ("a name twice in the block is fine", [(C, "        if s.name in seen:\n            problems.append", "        if False:\n            problems.append")]),
    ("class attributes are not names of the class", [(C, "        elif isinstance(n, ast.Assign):\n            for t in n.targets:\n                names |= {x.id for x in ast.walk(t) if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Store)}\n        elif isinstance(n, (ast.AnnAssign, ast.AugAssign)) and isinstance(n.target, ast.Name):\n            names.add(n.target.id)\n    return names\n\n\ndef insertion_problems",
                                                       "        pass\n    return names\n\n\ndef insertion_problems")]),
    ("an inherited name is not looked for", [(C, "    if not ins or ins.get(\"kind\") != \"class\":\n        return []\n    return [f\"inserted", "    return []\n    return [f\"inserted")]),
    ("an insertion that is not a class insertion has problems", [(C, "def insertion_problems(path, old, ins):\n    \"\"\"For a class insertion, whatever route made it: the class must be a top-level class bound once without decorators, and the\n    added statements may only be `def test*` methods with new names, no decorators, constant defaults. A name or helper inside\n    a TestCase changes how every old test of the class runs (setUp, run, an inherited or shadowed method).\"\"\"\n    if not ins or ins.get(\"kind\") != \"class\":\n        return []",
                                                                "def insertion_problems(path, old, ins):\n    \"\"\"x\"\"\"\n    if not ins:\n        return []")]),
    # the binding count
    ("a def does not bind its name", [(C, "        if isinstance(x, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and x.name == name:\n            n += 1", "        if isinstance(x, ast.ClassDef) and x.name == name:\n            n += 1")]),
    ("a store does not bind", [(C, "        elif isinstance(x, ast.Name) and x.id == name and isinstance(x.ctx, (ast.Store, ast.Del)):\n            n += 1", "        elif False:\n            n += 1")]),
    ("a del does not bind", [(C, "isinstance(x.ctx, (ast.Store, ast.Del)):\n            n += 1", "isinstance(x.ctx, ast.Store):\n            n += 1")]),
    ("an import does not bind", [(C, "        elif isinstance(x, ast.alias) and (x.asname or x.name.split(\".\")[0]) == name:\n            n += 1", "        elif False:\n            n += 1")]),
    ("except-as does not bind", [(C, "        elif isinstance(x, ast.ExceptHandler) and x.name == name:\n            n += 1", "        elif False:\n            n += 1")]),
    # the builder
    ("the feature is off", [(C, "        if \"into_class\" in e:\n            content, why = _insert_into", "        if False:\n            content, why = _insert_into")]),
    ("a none into_class is a mode", [(C, "if not (k in (\"content\", \"append\", \"into_class\") and v is None)", "if not (k in (\"content\", \"append\") and v is None)")]),
    ("into_class without append passes", [(C, "            if \"into_class\" in e:\n                problems.append(f\"changed_tests[{i}]: into_class goes with append\")\n                continue\n", "")]),
    ("into_class is an unknown key", [(C, "if set(e) - {\"path\", \"append\", \"into_class\", \"removed\", \"modified\"}", "if set(e) - {\"path\", \"append\", \"removed\", \"modified\"}")]),
    ("the class name is not checked", [(C, "if not isinstance(name, str) or not re.match(r\"^[A-Za-z_]\\w{0,99}$\", name):", "if not isinstance(name, str):")]),
    ("a carriage return is fine", [(C, "for ch_ in (\"\\r\", \"\\x0b\", \"\\x0c\"):", "for ch_ in (\"\\x0b\", \"\\x0c\"):")]),
    ("a form feed is fine", [(C, "for ch_ in (\"\\r\", \"\\x0b\", \"\\x0c\"):", "for ch_ in (\"\\r\", \"\\x0b\"):")]),
    ("a class bound twice is fine for the builder", [(C, "    if len(tops) != 1 or _bindings(tree, name) != 1:\n        return None, [", "    if len(tops) != 1:\n        return None, [")]),
    ("a decorated class is fine for the builder", [(C, "    if c.decorator_list:\n        return None, [", "    if False:\n        return None, [")]),
    ("a one-line class is fine", [(C, "    if first.lineno == c.lineno:\n        return None, [", "    if False:\n        return None, [")]),
    ("tabs are fine", [(C, "    if not indent or indent.strip(\" \") != \"\":", "    if not indent:")]),
    ("a comment-only block is fine", [(C, "    if not added.body:\n        return None, [", "    if False:\n        return None, [")]),
    ("the block is not dedented", [(C, "dedented = textwrap.dedent(block).strip(\"\\n\")", "dedented = block.strip(\"\\n\")")]),
    ("no blank line before the block", [(C, "lines[:c.end_lineno] + [\"\"] + body.split(\"\\n\")", "lines[:c.end_lineno] + body.split(\"\\n\")")]),
    ("the block goes before the last line of the class", [(C, "lines[:c.end_lineno] + [\"\"] + body.split(\"\\n\") + lines[c.end_lineno:]", "lines[:c.end_lineno - 1] + [\"\"] + body.split(\"\\n\") + lines[c.end_lineno - 1:]")]),
    ("the class of the result is not checked", [(C, "if ins is None or ins[\"class\"] != name:", "if ins is None:")]),
    ("a string that changes under the indentation is fine", [(C, "    if _dump(ins[\"stmts\"]) != _dump(added.body):", "    if False:")]),
    ("the whitelist is not applied by the builder", [(C, "    bad = insertion_problems(path, old, ins)\n    return", "    bad = []\n    return")]),
    ("the main guard refuses an insertion too", [(C, "        if \"into_class\" in e:\n            content, why = _insert_into(path, old, tree, e[\"into_class\"], block, where)\n            if why:\n                problems += why\n                continue\n        else:",
                                                   "        if \"into_class\" in e and not _main_guard(tree):\n            content, why = _insert_into(path, old, tree, e[\"into_class\"], block, where)\n            if why:\n                problems += why\n                continue\n        else:")]),
    # the draft-level checks
    ("an insertion is not checked statically", [(C, "        elif ins:\n            problems += insertion_problems", "        elif False:\n            problems += insertion_problems")]),
    ("an insertion is not a way to add a test", [(C, "        if old is None or not insertion(old, t[\"content\"]):", "        if old is None or not pure_addition(old, t[\"content\"]):")]),
    ("k1 is only for an append at the end", [(D, "            if ins:                                                   # SPEC_APPEND_TESTS rule 4, SPEC_INSERT_INTO: an insertion too", "            if ins and ins[\"kind\"] == \"end\":                          # x")]),
    ("an inherited override is not looked for", [(D, "                problems += ch.inherited_problems(p, ins, got[\"intake\"])", "                pass")]),
    # the old hole of an append at the end of a file
    ("the imports of the intake may be redefined", [(C, "(_top_names(before) | _import_names(before)) & _top_names(added)", "_top_names(before) & _top_names(added)")]),
    ("an import with as binds its module name", [(C, "names |= {(x.asname or x.name.split(\".\")[0]) for x in n.names}", "names |= {x.name.split(\".\")[0] for x in n.names}")]),
    ("a dotted import binds its whole name", [(C, "names |= {(x.asname or x.name.split(\".\")[0]) for x in n.names}", "names |= {(x.asname or x.name) for x in n.names}")]),
    ("an attribute assignment is fine", [(C, "    lines = _attribute_targets(added)\n    if lines:", "    lines = []\n    if lines:")]),
    ("an item assignment is fine", [(C, "if any(isinstance(x, (ast.Attribute, ast.Subscript)) for t in targets for x in ast.walk(t)):", "if any(isinstance(x, ast.Attribute) for t in targets for x in ast.walk(t)):")]),
    ("an attribute is only looked for in a plain assignment", [(C, "targets = n.targets if isinstance(n, (ast.Assign, ast.Delete)) else [n.target] if isinstance(n, (ast.AugAssign, ast.AnnAssign)) else []", "targets = n.targets if isinstance(n, ast.Assign) else []")]),
    ("a delete of an attribute is fine", [(C, "targets = n.targets if isinstance(n, (ast.Assign, ast.Delete))", "targets = n.targets if isinstance(n, ast.Assign)")]),
    ("only the first target of a tuple is looked at", [(C, "for t in targets for x in ast.walk(t)):", "for t in targets for x in [t]):")]),
    # what the drafter and the human see
    ("the schema has no into_class", [(R, "    into_class: Optional[str] = Field(default=None,", "    into_classx: Optional[str] = Field(default=None,")]),
    ("the prompt does not mention into_class", [(R, "add into_class with that class's name and write only its \"\n    \"methods in append", "add the class's name and write only its \"\n    \"methods in append")]),
    ("the prompt does not say only methods", [(R, "write only its \"\n    \"methods in append", "write the \"\n    \"code in append")]),
    ("the append field does not mention into_class", [(R, "(or, with \"\n                                  \"into_class, at the end of that class); the \"", "; the \"")]),
    ("the review shows an insertion as the whole class", [(R, "code = \"\\n\".join(t[\"content\"].split(\"\\n\")[ins[\"first\"] - 1:ins[\"last\"]])", "code = t[\"content\"]")]),
    ("the review calls an insertion an append", [(R, "where = (f\" (inserted at the end of class {t['into']} of the existing file)\" if t.get(\"into\")", "where = (f\" (added at the end of the existing file)\" if t.get(\"into\")")]),
    ("an insertion is not shown with the new tests", [(R, "        if ins[\"kind\"] == \"class\":\n            code =", "        if False:\n            code =")]),
    ("the human is not told which class", [(R, "(\"The methods inserted into the class:\" if t.get(\"into\")", "(\"The code added at the end of the file:\" if t.get(\"into\")")]),
]

# Mutants no test can kill because the code has a second, redundant defence (checked by experiment 2026-11-14 on eight varied inputs:
# the outcome of acceptance.changed.insertion / from_append is identical with and without the mutant). Reported as EQUIVALENT, not counted
# as killed.
TEXT = "the final text must equal the old text plus the added lines, which already refuses it"
EQUIVALENT = {
    "a module that gained a statement may be an insertion": TEXT + " (an extra top-level statement stays in the remainder)",
    "two classes may change": TEXT + " (the first changed class stays in the remainder)",
    "the class header may change": TEXT + " (a header line differs in the remainder)",
    "the old statements of the class may change": TEXT + " (an old line differs in the remainder)",
    "a class that only lost statements counts": "a class whose AST differs but whose header and old body are the same does not exist, so the branch is unreachable",
    "any trailing line belongs to the block": "a trailing line that is not a comment or blank is a statement: it changes the module AST and the body check refuses it first",
    "a class bound twice is fine for the builder": "insertion_problems, called by the builder right after, counts the bindings again and refuses it",
    "a decorated class is fine for the builder": "insertion_problems, called by the builder right after, refuses a decorated class",
    "a one-line class is fine": "the next check (the body must be indented with spaces) refuses it",
    "the class of the result is not checked": "the block is inserted into the class `name` only, so the class of the result can only be `name`",
}


if __name__ == "__main__":
    WT, PY = Path(sys.argv[1]), sys.argv[2]
    check_only = "--check" in sys.argv
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else ""
    todo = [m for m in M if only in m[0]]
    killed = equiv = 0
    for name, edits in todo:
        originals, texts = {}, {}
        for f, a, b in edits:
            texts.setdefault(f, (WT / f).read_text())
            originals.setdefault(f, texts[f])
            assert texts[f].count(a) == 1, (name, a[:70], texts[f].count(a))
            texts[f] = texts[f].replace(a, b, 1)
        if check_only:
            continue
        for f, t in texts.items():
            (WT / f).write_text(t)
        try:
            r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *T], cwd=WT,
                               capture_output=True, text=True, timeout=1800, env=os.environ)
        finally:
            for f, t in originals.items():
                (WT / f).write_text(t)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        fails = [line for line in r.stdout.splitlines() if line.startswith("FAILED tests/test_")][:1]
        k = bool(fails) and "error" not in last
        killed += k
        equiv += (not k) and name in EQUIVALENT
        verdict = "KILLED  " if k else "EQUIVALENT" if name in EQUIVALENT else "SKIPPED " if "skipped" in last and not fails else "ERROR   " if "error" in last else "SURVIVED"
        print(f"{verdict} {name}: {fails or last}", flush=True)
    print("patterns ok" if check_only else f"RESULT: {killed}/{len(todo) - equiv} killed, {equiv} equivalent (documented), {len(todo)} in all")
