"""Mutants for SPEC_CHAT_PACKAGES S1 (router/env_packages.py, the pure part of the package request). Applied alone; killed = a test FAILED.
Equivalent in behaviour (documented): "a name of 33 characters is accepted" (the environment shape allows at most 32, a second guard).
Run in a throwaway worktree. Usage: <this> <worktree> <python> [name-part ...]   (a name part re-runs only the mutants whose name contains it)"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
ONLY = sys.argv[3:]
F = "router/env_packages.py"
T = ["-rfEs", "tests/test_env_packages.py"]
M = [
    ("the version may lose its patch part", F, [('VERSION = r"[0-9]+\\.[0-9]+\\.[0-9]+"', 'VERSION = r"[0-9]+\\.[0-9]+(?:\\.[0-9]+)?"')]),
    ("the digits are any script's digits", F, [('VERSION = r"[0-9]+\\.[0-9]+\\.[0-9]+"', 'VERSION = r"\\d+\\.\\d+\\.\\d+"'), ('LINE = re.compile(rf"({NAME})(?:@({VERSION}))?", re.ASCII)', 'LINE = re.compile(rf"({NAME})(?:@({VERSION}))?")')]),
    ("a line is matched, not fully matched", F, [("LINE.fullmatch(line) if len(line) <= LINE_MAX else None", "LINE.match(line) if len(line) <= LINE_MAX else None")]),
    ("six lines are accepted", F, [("LINES_MAX = 5", "LINES_MAX = 6")]),
    ("the text length is not bounded", F, [("    if len(text) > TEXT_MAX:\n        return None, f\"the request is longer than {TEXT_MAX} characters\"\n", "")]),
    ("the line length is not bounded", F, [("LINE.fullmatch(line) if len(line) <= LINE_MAX else None", "LINE.fullmatch(line)")]),
    ("a name may repeat", F, [("        if name in seen:\n            return None, f\"{name} appears twice\"\n", "")]),
    ("blank lines are kept", F, [("    lines = [l for l in lines if l]\n", "")]),
    ("lines are not stripped", F, [("    lines = [l.strip() for l in text.replace(\"\\r\", \"\").split(\"\\n\")]", "    lines = [l for l in text.replace(\"\\r\", \"\").split(\"\\n\")]")]),
    ("a lone carriage return is removed", F, [('text.split("\\n")]       #', 'text.replace("\\r", "").split("\\n")]       #')]),
    ("a request that is not text crashes", F, [("    if not isinstance(text, str):\n        return None, \"the request is not text\"\n", "")]),
    ("a nested locked name is read wrongly", F, [('names.add(key.rsplit("node_modules/", 1)[1])', 'names.add(key.split("node_modules/")[1])')]),
    ("a locked name is not refused", F, [("        if it[\"name\"] in have:\n            return f\"{it['name']} is already in the environment: an upgrade is not offered\"", "        if False:\n            return None")]),
    ("lockfile version 3 is not required", F, [('    if new.get("lockfileVersion") != 3 or old.get("lockfileVersion") != 3:', "    if False:")]),
    ("a key without a package path shape is accepted", F, [("        if key_name(key) is None:\n            blocks.append(\"a lock key does not have the shape of a package path\")\n            continue", "        if key_name(key) is None:\n            continue")]),
    ("a non-object entry is accepted", F, [("        if not isinstance(entry, dict):\n            blocks.append(f\"the entry of {key_name(key)} is not an object\")\n            continue", "        if not isinstance(entry, dict):\n            continue")]),
    ("a link is accepted", F, [('        if entry.get("link") is True:', "        if False:")]),
    ("an alias is accepted", F, [('        if "name" in entry and entry.get("name") != key_name(key):', "        if False:")]),
    ("a version change of an existing entry is not seen", F, [('COMPARED = ("version", "resolved"', 'COMPARED = ("resolved"')]),
    ("an integrity change is not seen", F, [('"integrity", "dev"', '"dev"')]),
    ("a resolved change is not seen", F, [('"version", "resolved", "integrity"', '"version", "integrity"')]),
    ("a dev flag flip is not seen", F, [('"integrity", "dev", "optional"', '"integrity", "optional"')]),
    ("an optional flag flip is not seen", F, [('"dev", "optional", "devOptional"', '"dev", "devOptional"')]),
    ("a devOptional flag flip is not seen", F, [('"optional", "devOptional", "peer")', '"optional", "peer")')]),
    ("a peer flag flip is not seen", F, [('"devOptional", "peer")', '"devOptional")')]),
    ("a change of an existing entry is not a block", F, [("    if changed:\n        blocks.append(", "    if False:\n        blocks.append(")]),
    ("a removed entry is not a block", F, [("    if removed:\n        blocks.append(", "    if False:\n        blocks.append(")]),
    ("a second copy at another version is accepted", F, [("        if n in old_versions and v not in old_versions[n]:", "        if False:")]),
    ("a second copy at the same version is a block", F, [("        if n in old_versions and v not in old_versions[n]:", "        if n in old_versions:")]),
    ("a package not from the registry is accepted", F, [("        if entry.get(\"inBundle\") is not True and not _fetched(entry):", "        if False:")]),
    ("the sha512 is not required", F, [('str(entry.get("integrity", "")).startswith("sha512-") and ', "")]),
    ("any host is the registry", F, [('str(entry.get("resolved", "")).startswith(REGISTRY)', '"registry.npmjs.org" in str(entry.get("resolved", ""))')]),
    ("the version shape of a new entry is not checked", F, [('        if not isinstance(v, str) or not LOCK_VERSION.fullmatch(v):\n            blocks.append(f"{n} has a version that is not a version")', '        if False:\n            blocks.append(f"{n} has a version that is not a version")')]),
    ("a requested package may be nested", F, [("        if e is None:\n            blocks.append(f\"{r['name']} is not a top-level package of the candidate\")", "        if False:\n            blocks.append('x')")]),
    ("a requested version mismatch is accepted", F, [("        elif r[\"version\"] is not None and e.get(\"version\") != r[\"version\"]:", "        elif False:")]),
    ("the age is read from modified", F, [("published, created = _when(time.get(version)), _when(time.get(\"created\"))", "published, created = _when(time.get(\"modified\")), _when(time.get(\"created\"))")]),
    ("the first publish is read from the version time", F, [("published, created = _when(time.get(version)), _when(time.get(\"created\"))", "published, created = _when(time.get(version)), _when(time.get(version))")]),
    ("the time shape is not checked", F, [("    if not isinstance(value, str) or not TIME.fullmatch(value):\n        return None", "    if not isinstance(value, str):\n        return None")]),
    ("a license is matched, not fully matched", F, [("    return value if isinstance(value, str) and LICENSE.fullmatch(value) else None", "    return value if isinstance(value, str) and LICENSE.match(value) else None")]),
    ("a license object is not read", F, [("    if isinstance(value, dict):\n        value = value.get(\"type\")\n", "")]),
    ("a bool is a size", F, [("size if isinstance(size, int) and not isinstance(size, bool) and 0 <= size <= SIZE_MAX else None", "size if isinstance(size, int) and 0 <= size <= SIZE_MAX else None")]),
    ("the size is not bounded", F, [("and not isinstance(size, bool) and 0 <= size <= SIZE_MAX", "and not isinstance(size, bool) and 0 <= size")]),
    ("the maintainers count is not capped", F, [("min(len(maint), MAINTAINERS_MAX)", "len(maint)")]),
    ("the deprecation message is kept", F, [('"deprecated": bool(v.get("deprecated")),', '"deprecated": v.get("deprecated") or False,')]),
    ("a duplicate key in a view is accepted", F, [("json.loads(text, object_pairs_hook=_no_dupes)", "json.loads(text)")]),
    ("a huge view is accepted", F, [(" or len(text) > 5_000_000:", ":")]),
    ("a view that is not an object is accepted", F, [("    return v if isinstance(v, dict) else None", "    return v")]),
    ("the age limit is exclusive", F, [("        elif f[\"age_days\"] < lim[\"min_age_days\"]:", "        elif f[\"age_days\"] <= lim[\"min_age_days\"]:")]),
    ("an unknown age is not a block", F, [("        if f[\"age_days\"] is None:\n            blocks.append(f\"{label} has no publish time: its age is unknown\")\n        elif", "        if f[\"age_days\"] is None:\n            pass\n        elif")]),
    ("a package without a record is not a block", F, [("        if view is None or not isinstance(view, dict):\n            blocks.append(f\"{label} has no registry record\")\n            continue", "        if view is None or not isinstance(view, dict):\n            continue")]),
    ("only the requested packages are judged", F, [("    for key in sorted(entries, key=lambda k: (key_name(k) or \"\", k)):", "    for key in sorted([k for k in entries if key_name(k) in direct_names], key=lambda k: (key_name(k) or \"\", k)):")]),
    ("the limit of new packages is exclusive", F, [("    if len(entries) > lim[\"max_new\"]:", "    if len(entries) >= lim[\"max_new\"]:")]),
    ("the limit of new packages is not applied", F, [("    if len(entries) > lim[\"max_new\"]:", "    if False:")]),
    ("a deprecated package is not warned", F, [("        if f[\"deprecated\"]:\n            warns.append", "        if False:\n            warns.append")]),
    ("an install script is not warned", F, [("        if packages[-1][\"has_install_script\"]:", "        if False:")]),
    ("an unreadable license is not warned", F, [("        if f[\"license\"] is None:\n            warns.append", "        if False:\n            warns.append")]),
    ("a non-permissive license is not warned", F, [("        elif not permissive(f[\"license\"]):", "        elif False:")]),
    ("a recent first publish is not warned", F, [("        if f[\"created_days\"] is not None and f[\"created_days\"] < lim[\"new_package_days\"]:", "        if False:")]),
    ("the new-package warning is inclusive", F, [("f[\"created_days\"] < lim[\"new_package_days\"]:", "f[\"created_days\"] <= lim[\"new_package_days\"]:")]),
    ("a refused report is OK", F, [('"status": "REFUSED" if blocks else "OK"', '"status": "OK"')]),
    ("the blocks of the lock are dropped", F, [("    blocks, warns, packages = list(a[\"blocks\"]), [], []", "    blocks, warns, packages = [], [], []")]),
    ("the direct count is every package", F, [('"direct": sum(1 for p in packages if p["direct"])', '"direct": len(packages)')]),
    ("a nested package is direct", F, [("        direct = key == f\"node_modules/{n}\" and n in direct_names", "        direct = n in direct_names")]),
    ("the warnings are not deduplicated", F, [('"warns": _dedupe(warns)', '"warns": warns')]),
    ("the blocks are not deduplicated", F, [('"blocks": _dedupe(blocks), "warns"', '"blocks": blocks, "warns"')]),
    ("the packages are not sorted", F, [("    for key in sorted(entries, key=lambda k: (key_name(k) or \"\", k)):", "    for key in entries:")]),
    ("the base keeps its suffix", F, [("    stem = UP_SUFFIX.sub(\"\", base)", "    stem = base")]),
    ("the numbering starts at zero", F, [("    for n in range(1, UP_MAX + 1):", "    for n in range(0, UP_MAX + 1):")]),
    ("a taken name is reused", F, [("        if name not in taken:\n            return name, None", "        if True:\n            return name, None")]),
    ("a long name is not refused", F, [("        if len(name) > ENV_NAME_MAX or not ENV_NAME.fullmatch(name):", "        if False:")]),
    ("a name of 33 characters is accepted", F, [("        if len(name) > ENV_NAME_MAX or not", "        if len(name) > ENV_NAME_MAX + 1 or not")]),
    ("the base shape is not checked", F, [("    if not isinstance(base, str) or not ENV_NAME.fullmatch(base):\n        return None, \"the base is not an environment name\"\n", "")]),
    ("the numbering has no end", F, [("UP_MAX = 99", "UP_MAX = 10 ** 6")]),
    ("a bool is a limit", F, [("        if isinstance(v, int) and not isinstance(v, bool) and lo <= v <= hi:", "        if isinstance(v, int) and lo <= v <= hi:")]),
    ("a limit out of range is accepted", F, [("        if isinstance(v, int) and not isinstance(v, bool) and lo <= v <= hi:", "        if isinstance(v, int) and not isinstance(v, bool):")]),
    ("the lock sha is not sha256", F, [("    return hashlib.sha256(", "    return hashlib.sha1(")]),
    ("the default age limit is seven days", F, [('DEFAULTS = {"min_age_days": 14,', 'DEFAULTS = {"min_age_days": 7,')]),
    ("the default new-package limit is larger", F, [('"max_new": 200,', '"max_new": 300,')]),
]
killed = ran = 0
for name, f, edits in M:
    if ONLY and not any(o in name for o in ONLY):
        continue
    ran += 1
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
print(f"RESULT: {killed}/{ran} killed")
