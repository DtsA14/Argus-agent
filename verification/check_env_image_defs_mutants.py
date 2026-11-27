"""Mutants for SPEC_CHAT_PACKAGES S0 (scripts/check_env_image.py checks an environment that is not adopted yet). Applied alone; killed = a test FAILED.
Run in a throwaway worktree, never in the live checkout: a mutant that writes a check record must not reach the real pins.
Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
F = "scripts/check_env_image.py"
T = ["-rfEs", "tests/test_check_env_image_defs.py", "tests/test_env_node.py"]
M = [
    ("the check record default root is bound at definition", F, [('def record_path(name, root=None):\n    return Path(ROOT if root is None else root)', 'def record_path(name, root=ROOT):\n    return Path(root)')]),
    ("the definition folder ignores a staged one", F, [("    return Path(defs) / name if defs is not None else Path(ROOT if root is None else root) / \"environments\" / name", "    return Path(ROOT if root is None else root) / \"environments\" / name")]),
    ("the lock is read from the checkout when staged", F, [("    want = locked(name) if defs is None else locked(name, defs=defs)", "    want = locked(name)")]),
    ("the requirements are read from the checkout when staged", F, [("    want = pinned(name) if defs is None else pinned(name, defs=defs)", "    want = pinned(name)")]),
    ("the vitest build metadata is read from the checkout", F, [('    meta_path = pins / f".sandbox_image_{name}.json"\n    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}\n    want = locked(name)', '    meta_path = ROOT / f".sandbox_image_{name}.json"\n    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}\n    want = locked(name)')]),
    ("the python build metadata is read from the checkout", F, [('    meta_path = pins / f".sandbox_image_{name}.json"\n    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}\n    ver_ok = bool(probe) and probe["pytest"]', '    meta_path = ROOT / f".sandbox_image_{name}.json"\n    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}\n    ver_ok = bool(probe) and probe["pytest"]')]),
    ("an inherited image variable is kept", F, [('    os.environ.pop(f"ARGUS_SANDBOX_IMAGE_{o.name.upper()}", None)\n', "")]),
    ("a configured name is accepted with the options", F, [("    if o.name in envs:\n", "    if False:\n")]),
    ("the options need only one of the three", F, [("    if not (o.defs and o.out and o.like):", "    if not (o.defs or o.out or o.like):")]),
    ("an unknown --like is accepted", F, [("    if not isinstance(envs.get(o.like), dict):", "    if False:")]),
    ("the overlay keeps the image of the base", F, [('{**envs[o.like], "image": image}}}, image, defs, out, None', '{**envs[o.like]}}}, image, defs, out, None')]),
    ("the overlay copies nothing of the base block", F, [('{**envs[o.like], "image": image}}}, image, defs, out, None', '{"image": image}}}, image, defs, out, None')]),
    ("the overlay is written into the config it was given", F, [('    return {**cfg, "environments": {**envs, o.name: {**envs[o.like], "image": image}}}, image, defs, out, None', '    envs[o.name] = {**envs[o.like], "image": image}\n    return cfg, image, defs, out, None')]),
    ("a pin that only starts with a digest is accepted", F, [("    return text if PIN_DIGEST.fullmatch(text) else None", "    return text if PIN_DIGEST.match(text) else None")]),
    ("a linked pin file is accepted", F, [("        if path.is_symlink() or not path.is_file()", "        if not path.is_file()")]),
    ("a huge pin file is accepted", F, [(" or path.stat().st_size > 512:", ":")]),
    ("the record is written in the checkout when staged", F, [('        extra, where = {"defs": defs, "out": out}, out', '        extra, where = {"defs": defs, "out": out}, ROOT')]),
    ("a stale record is kept", F, [("    record_path(o.name, where).unlink(missing_ok=True)\n", "")]),
    ("a record is written on a failure", F, [("    if ok:\n        record_path(o.name, where).write_text(", "    if True:\n        record_path(o.name, where).write_text(")]),
    ("the checks do not get the staged folders", F, [('        extra, where = {"defs": defs, "out": out}, out', "        extra, where = {}, out")]),
    ("the name shape is not checked", F, [("    if not sb.ENV_NAME.match(o.name):", "    if False:")]),
    ("a missing out directory is accepted", F, [(" or not out.is_dir():", ":")]),
    ("a missing definition folder is accepted", F, [("    if not (defs / o.name).is_dir() or not out.is_dir():", "    if not out.is_dir():")]),
    ("the old form passes new keywords", F, [("    extra, where = {}, ROOT", '    extra, where = {"defs": None, "out": None}, ROOT')]),
    ("the old form skips the definition folder test", F, [(" or not (ROOT / \"environments\" / o.name).is_dir():", ":")]),
    ("the old form writes its record in the staged place", F, [("    extra, where = {}, ROOT", "    extra, where = {}, Path(o.out or ROOT)")]),
    ("a free --runner option exists", F, [('    ap.add_argument("--like",', '    ap.add_argument("--runner")\n    ap.add_argument("--like",')]),
]
killed = 0
for name, f, edits in M:
    p = WT / f
    orig = p.read_text()
    text = orig
    if any(text.count(a) != 1 for a, _ in edits):
        print("STALE  ", name, flush=True)
        continue
    for a, b in edits:
        text = text.replace(a, b, 1)
    p.write_text(text)
    try:
        r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *T], cwd=WT, capture_output=True, text=True, timeout=900,
                           env={**__import__("os").environ, "PYTHONPATH": f"{WT}:{WT}/scripts"})
    finally:
        p.write_text(orig)
    last = (r.stdout.strip().splitlines() or [""])[-1]
    k = "FAILED tests/" in r.stdout or "FAILED" in last or "error" in last.lower()
    killed += k
    print("KILLED " if k else "SURVIVED", name, flush=True)
print(f"RESULT: {killed}/{len(M)} killed")
