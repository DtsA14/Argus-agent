"""Mutants for APPEND-TESTS (acceptance/changed.py, acceptance/draft.py, codetask/drafter.py; SPEC_APPEND_TESTS): each applied alone in a
worktree, tests/test_append_tests.py runs with -x (its two sandbox tests need ARGUS_SANDBOX_IMAGE_ARGUS in the environment);
killed = a test FAILED and pytest reported no error. Usage: <this> <worktree> <python>   (--check: only count the patterns)"""
import os
import subprocess
import sys
from pathlib import Path

C, D, R = "acceptance/changed.py", "acceptance/draft.py", "codetask/drafter.py"
T = ["-rfEs", "tests/test_append_tests.py", "tests/test_append_tests_sandbox.py"]
M = [
    # the builder
    ("the block limit is dropped", [(C, 'if len(block.encode("utf-8")) > limit:', "if False:")]),
    ("the block limit counts characters", [(C, 'if len(block.encode("utf-8")) > limit:', "if len(block) > limit:")]),
    ("the final newlines of the intake are kept", [(C, 'content = old.rstrip("\\n") + "\\n\\n\\n"', 'content = old + "\\n\\n\\n"')]),
    ("one blank line instead of two", [(C, 'content = old.rstrip("\\n") + "\\n\\n\\n"', 'content = old.rstrip("\\n") + "\\n\\n"')]),
    ("the block is not stripped", [(C, 'block.strip("\\n") + "\\n"\n        if len(content', 'block + "\\n"\n        if len(content')]),
    ("no final newline", [(C, 'block.strip("\\n") + "\\n"\n        if len(content', 'block.strip("\\n")\n        if len(content')]),
    ("the mebibyte cap is dropped", [(C, 'if len(content.encode("utf-8")) > MAX_CHANGED_BYTES:', "if False:")]),
    ("the mebibyte cap counts characters", [(C, 'if len(content.encode("utf-8")) > MAX_CHANGED_BYTES:', "if len(content) > MAX_CHANGED_BYTES:")]),
    ("a main guard is accepted", [(C, "if _main_guard(tree):", "if False:")]),
    ("a main guard is found at any depth", [(C, "    for n in tree.body:\n        if isinstance(n, ast.If) and isinstance(n.test, ast.Compare)",
                                             "    for n in ast.walk(tree):\n        if isinstance(n, ast.If) and isinstance(n.test, ast.Compare)")]),
    ("only the name on the left is a main guard", [(C, 'sides = [n.test.left, *n.test.comparators]', 'sides = [n.test.left, n.test.left]')]),
    ("content and append together are accepted", [(C, 'if "content" in e:\n            problems.append(f"{where}: give exactly one', 'if False:\n            problems.append(f"{where}: give exactly one')]),
    ("removed and modified are accepted with append", [(C, 'if e.get("removed") or e.get("modified"):', "if False:")]),
    ("a none content or append is kept", [(C, 'if not (k in ("content", "append") and v is None)', "if True")]),
    ("a blank block is accepted", [(C, "if not isinstance(block, str) or not block.strip():", "if not isinstance(block, str):")]),
    ("an unknown key is accepted", [(C, 'if set(e) - {"path", "append", "removed", "modified"} or not isinstance(e.get("path"), str):', 'if not isinstance(e.get("path"), str):')]),
    ("the path need not be plain", [(C, "if not plain(path):", "if False:")]),
    # pure addition and sizes
    ("a pure addition need not keep the old text", [(C, 'return new.startswith(base + "\\n") and new[len(base):].strip() != ""', 'return new.strip() != ""')]),
    ("nothing added still counts as a pure addition", [(C, 'return new.startswith(base + "\\n") and new[len(base):].strip() != ""', 'return new.startswith(base + "\\n")')]),
    ("the old text need not be followed by a newline", [(C, 'return new.startswith(base + "\\n") and', "return new.startswith(base) and")]),
    ("added bytes keep the final newlines of the intake", [(C, 'len(old.rstrip("\\n").encode("utf-8"))', 'len(old.encode("utf-8"))')]),
    ("added bytes are characters", [(C, 'return len(new.encode("utf-8")) - len(old.rstrip', "return len(new) - len(old.rstrip")]),
    ("the overhead is not allowed", [(C, "> MAX_BLOCK_BYTES + APPEND_OVERHEAD)", "> MAX_BLOCK_BYTES)")]),
    ("the fifty thousand is dropped for a file that is not a pure addition", [(C, 'else (len(t["content"].encode("utf-8")) > MAX_BLOCK_BYTES):', "else False:")]),
    ("the total counts for a pure addition", [(C, "if (added_bytes(old_tests[p], t[\"content\"]) > MAX_BLOCK_BYTES + APPEND_OVERHEAD) if pure \\\n                else",
                                                 "if (len(t[\"content\"].encode(\"utf-8\")) > MAX_BLOCK_BYTES + APPEND_OVERHEAD) if pure \\\n                else")]),
    # no new file
    ("a draft without new_tests needs nothing", [(C, 'if not draft["new_tests"] and not _adds_a_test(draft, contract, old_tests):', "if False:")]),
    ("an old test counts as the required new one", [(C, "if required - have:", "if required:")]),
    ("a changed file that is not a pure addition counts", [(C, "if old is None or not pure_addition(old, t[\"content\"]):", "if old is None:")]),
    ("only Test classes are known tests", [(C, "        elif isinstance(n, ast.ClassDef):\n            out |=", "        elif isinstance(n, ast.ClassDef) and n.name.startswith(\"Test\"):\n            out |=")]),
    # K1
    ("an already collected required node is accepted", [(C, "for n in required if n in before or func_key(n) in old]", "for n in required if False]")]),
    ("a parametrised node is compared whole", [(C, "for n in required if n in before or func_key(n) in old]", "for n in required if n in before]")]),
    ("the k1 rule is dropped", [(D, "if old_text is not None and ch.pure_addition(old_text, t[\"content\"]):", "if False:")]),
    ("the k1 rule holds for every changed file", [(D, "if old_text is not None and ch.pure_addition(old_text, t[\"content\"]):", "if old_text is not None:")]),
    # the draft
    ("a draft may be empty of tests", [(D, "if not isinstance(tests, list) or (not tests and not (isinstance(changes, list) and changes)):", "if not isinstance(tests, list):")]),
    ("new_tests stays required", [(D, "if not isinstance(tests, list) or (not tests and not (isinstance(changes, list) and changes)):", "if not isinstance(tests, list) or not tests:")]),
    ("an empty changed_tests lets new_tests be empty", [(D, "(not tests and not (isinstance(changes, list) and changes))", "(not tests and not isinstance(changes, list))")]),
    ("the draft cap is fifty thousand again", [(D, "ch.shape_problems(d[\"changed_tests\"], new_paths, intake._plain, ch.MAX_CHANGED_BYTES)", "ch.shape_problems(d[\"changed_tests\"], new_paths, intake._plain, MAX_TEST_BYTES)")]),
    ("the draft cap is gone", [(D, "ch.shape_problems(d[\"changed_tests\"], new_paths, intake._plain, ch.MAX_CHANGED_BYTES)", "ch.shape_problems(d[\"changed_tests\"], new_paths, intake._plain, 1 << 40)")]),
    # an addition keeps every old definition
    ("a redefinition is accepted", [(C, "            problems += redefined_problems(p, old_tests[p], t[\"content\"])", "            pass")]),
    ("classes are not top-level names", [(C, "if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):\n            names.add(n.name)", "if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):\n            names.add(n.name)")]),
    ("functions are not top-level names", [(C, "if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):\n            names.add(n.name)", "if isinstance(n, ast.ClassDef):\n            names.add(n.name)")]),
    ("assignments are not top-level names", [(C, "        elif isinstance(n, ast.Assign):\n            for t in n.targets:", "        elif False:\n            for t in n.targets:")]),
    ("a tuple target binds nothing", [(C, "for x in ast.walk(t) if isinstance(x, ast.Name)", "for x in [t] if isinstance(x, ast.Name)")]),
    ("an augmented assignment binds nothing", [(C, "elif isinstance(n, (ast.AnnAssign, ast.AugAssign)) and", "elif isinstance(n, ast.AnnAssign) and")]),
    ("the whole new file is read as the addition", [(C, 'before, added = ast.parse(old), ast.parse(new[len(old.rstrip("\\n")):])', "before, added = ast.parse(old), ast.parse(new)")]),
    ("the added code is not parsed", [(C, 'before, added = ast.parse(old), ast.parse(new[len(old.rstrip("\\n")):])', "before, added = ast.parse(old), ast.parse('')")]),
    ("empty removed and modified are kept", [(C, 'and not (k in ("removed", "modified") and v == [])', "and True")]),
    ("new_tests is required of the model again", [(R, "new_tests: List[NewTest] = Field(default_factory=list, description", "new_tests: List[NewTest] = Field(description")]),
    # what the human reads
    ("the review ignores appended tests for the split", [(R, 'new_paths = {t["path"] for t in draft["new_tests"]} | {a["path"] for a in appended}', 'new_paths = {t["path"] for t in draft["new_tests"]}')]),
    ("the review lists no appended section", [(R, 'for t in [*draft["new_tests"], *appended]:', 'for t in draft["new_tests"]:')]),
    ("the review shows the whole file as the appended code", [(R, '"content": t["content"][len(old.rstrip("\\n")):].lstrip("\\n"), "appended": True}', '"content": t["content"], "appended": True}')]),
    ("an edited file counts as appended", [(R, "if old is not None and ch.pure_addition(old, t[\"content\"]):\n            out.append", "if old is not None:\n            out.append")]),
    # the drafter
    ("append is not built", [(R, 'if isinstance(args.get("changed_tests"), list):', "if False:")]),
    ("the intake is not given to the build", [(R, "lambda p: _intake_text(intake_dir, p), intake._plain,", "lambda p: _intake_text(None, p), intake._plain,")]),
    ("submit does not pass the intake", [(R, "policy=policy, intake_dir=intake_dir,\n", "policy=policy,\n")]),
    ("the problems of the build are dropped", [(R, "        problems += why\n        args = {**args", "        args = {**args")]),
    ("new_tests is not defaulted", [(R, '"new_tests": args.get("new_tests") or [],', '"new_tests": args.get("new_tests"),')]),
    ("the schema has no append", [(R, "    append: Optional[str] = Field(default=None,", "    appendx: Optional[str] = Field(default=None,")]),
    ("the prompt does not mention append", [(R, "a changed_tests entry with path and append (only the new test code;", "a changed_tests entry with path and content (only the new test code;")]),
]

if __name__ == "__main__":
    WT, PY = Path(sys.argv[1]), sys.argv[2]
    check_only = "--check" in sys.argv
    killed = 0
    for name, edits in M:
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
        verdict = "KILLED  " if k else "SKIPPED " if "skipped" in last and not fails else "ERROR   " if "error" in last else "SURVIVED"
        print(f"{verdict} {name}: {fails or last}", flush=True)
    print("patterns ok" if check_only else f"RESULT: {killed}/{len(M)} killed")
