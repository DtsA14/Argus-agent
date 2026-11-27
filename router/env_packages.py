"""The pure part of the package request (docs/reviews/SPEC_CHAT_PACKAGES.md rev 2, S1): the parser of the request lines, the analysis of a candidate
lock against the environment's lock, the facts read from the registry's `npm view` output, the gates, the report and the name of the new environment.

Nothing here runs a process, touches the network or reads a file: every function takes its data and returns a value, so the one place that
decides what a human is shown, and what is refused, can be tested without Docker. The registry's output, the lock and the request text are DATA:
only values that fullmatch a strict shape are kept, and a value that does not is a problem, never repaired. No free text of the registry (a
description, a readme, a deprecation message, a funding URL) is ever returned."""
import hashlib
import json
import re
from datetime import datetime, timezone

DEFAULTS = {"min_age_days": 14, "max_new": 200, "new_package_days": 90}
LINES_MAX = 5
TEXT_MAX = 600
LINE_MAX = 200
NAME_PART = r"[a-z0-9][a-z0-9._-]{0,63}"
NAME = rf"(?:@{NAME_PART}/)?{NAME_PART}"
VERSION = r"[0-9]+\.[0-9]+\.[0-9]+"
LINE = re.compile(rf"({NAME})(?:@({VERSION}))?", re.ASCII)
NAME_RE = re.compile(NAME, re.ASCII)
KEY = re.compile(rf"node_modules/{NAME}(?:/node_modules/{NAME})*", re.ASCII)
LOCK_VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]{1,64})?(?:\+[0-9A-Za-z.-]{1,64})?", re.ASCII)
TIME = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?Z", re.ASCII)
LICENSE = re.compile(r"[A-Za-z0-9.()+ -]{1,60}", re.ASCII)
PERMISSIVE = {"MIT", "ISC", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0", "0BSD", "BlueOak-1.0.0", "CC0-1.0", "Unlicense", "Python-2.0"}
REGISTRY = "https://registry.npmjs.org/"
SIZE_MAX = 10 ** 12
MAINTAINERS_MAX = 1000
COMPARED = ("version", "resolved", "integrity", "dev", "optional", "devOptional", "peer")
ENV_NAME = re.compile(r"[a-z][a-z0-9_]{0,31}")
UP_SUFFIX = re.compile(r"_up[0-9]+$")
ENV_NAME_MAX = 32
UP_MAX = 99


def limits(cfg=None):
    """The limits: DEFAULTS, overridden by the config block `env_packages` when its values are whole numbers in a sane range; anything else is ignored."""
    out = dict(DEFAULTS)
    block = (cfg or {}).get("env_packages") if isinstance(cfg, dict) else None
    for k, (lo, hi) in {"min_age_days": (1, 365), "max_new": (1, 1000), "new_package_days": (0, 3650)}.items():
        v = block.get(k) if isinstance(block, dict) else None
        if isinstance(v, int) and not isinstance(v, bool) and lo <= v <= hi:
            out[k] = v
    return out


# ---- the request ------------------------------------------------------------------------------------------------------

def parse_lines(text):
    """(items, problem). `items` is a list of {"name", "version"} (version None for a name-only line), at most LINES_MAX, names distinct. A line is
    a registry name with an optional exact stable version: no range, tag, prerelease, build metadata, URL, git, file, alias or `npm:` form. A line
    that does not parse is a problem the human sees, never a repaired line. Digits are ASCII only."""
    if not isinstance(text, str):
        return None, "the request is not text"
    if len(text) > TEXT_MAX:
        return None, f"the request is longer than {TEXT_MAX} characters"
    lines = [l.strip() for l in text.replace("\r", "").split("\n")]
    lines = [l for l in lines if l]
    if not lines:
        return None, "the request has no package line"
    if len(lines) > LINES_MAX:
        return None, f"the request has more than {LINES_MAX} package lines"
    items, seen = [], set()
    for n, line in enumerate(lines, 1):
        m = LINE.fullmatch(line) if len(line) <= LINE_MAX else None
        if m is None:
            return None, f"line {n} is not a registry name with an optional exact version (x.y.z)"
        name, version = m.group(1), m.group(2)
        if name in seen:
            return None, f"{name} appears twice"
        seen.add(name)
        items.append({"name": name, "version": version})
    return items, None


def locked_names(lock):
    """The set of package names in a lock (every path), for the refusal of a name that is already locked."""
    names = set()
    for key in ((lock or {}).get("packages") or {}):
        if isinstance(key, str) and KEY.fullmatch(key):
            names.add(key.rsplit("node_modules/", 1)[1])
    return names


def refuse_locked(items, lock):
    """A problem when a requested name is already in the environment's lock (an upgrade is not in v1), else None."""
    have = locked_names(lock)
    for it in items:
        if it["name"] in have:
            return f"{it['name']} is already in the environment: an upgrade is not offered"
    return None


# ---- the lock ---------------------------------------------------------------------------------------------------------

def key_name(key):
    """The package name a lock key ends in, or None when the key has no valid shape."""
    return key.rsplit("node_modules/", 1)[1] if isinstance(key, str) and KEY.fullmatch(key) else None


def _fetched(entry):
    return str(entry.get("integrity", "")).startswith("sha512-") and str(entry.get("resolved", "")).startswith(REGISTRY)


def analyse(old, new, requested=()):
    """The facts of a candidate lock against the environment's lock, as a dict: `blocks` (strings, each a reason to refuse), `new` ({key: entry}),
    `changed` and `removed` (keys), `warns` is not here (the registry facts add them). Pure; the lock is data and nothing from it is returned
    except keys that matched the key shape and the checked fields of entries."""
    blocks = []
    if not isinstance(old, dict) or not isinstance(new, dict):
        return {"blocks": ["a lock is not an object"], "new": {}, "changed": [], "removed": []}
    if new.get("lockfileVersion") != 3 or old.get("lockfileVersion") != 3:
        blocks.append("a lock is not lockfile version 3")
    po, pn = old.get("packages"), new.get("packages")
    if not isinstance(po, dict) or not isinstance(pn, dict):
        return {"blocks": blocks + ["a lock has no packages"], "new": {}, "changed": [], "removed": []}
    for key, entry in pn.items():
        if key == "":
            continue
        if key_name(key) is None:
            blocks.append("a lock key does not have the shape of a package path")
            continue
        if not isinstance(entry, dict):
            blocks.append(f"the entry of {key_name(key)} is not an object")
            continue
        if entry.get("link") is True:
            blocks.append(f"{key_name(key)} is a link, not a registry package")
        if "name" in entry and entry.get("name") != key_name(key):
            blocks.append(f"{key_name(key)} is an alias of another package")
    if blocks and any("shape of a package path" in b or "is not an object" in b for b in blocks):
        return {"blocks": _dedupe(blocks), "new": {}, "changed": [], "removed": []}
    new_entries, changed, removed = {}, [], []
    for key in po:
        if key == "":
            continue
        if key not in pn:
            removed.append(key)
    for key, entry in pn.items():
        if key == "":
            continue
        if key in po:
            before = po[key] if isinstance(po[key], dict) else {}
            if any(before.get(f) != entry.get(f) for f in COMPARED):
                changed.append(key)
        else:
            new_entries[key] = entry
    if changed:
        blocks.append("an existing locked package changes: " + ", ".join(sorted(key_name(k) for k in changed)[:10]))
    if removed:
        blocks.append("an existing locked package is removed: " + ", ".join(sorted(key_name(k) for k in removed if key_name(k))[:10]))
    old_versions = {}
    for key, entry in po.items():
        n = key_name(key)
        if n and isinstance(entry, dict):
            old_versions.setdefault(n, set()).add(entry.get("version"))
    for key, entry in new_entries.items():
        n, v = key_name(key), entry.get("version")
        if not isinstance(v, str) or not LOCK_VERSION.fullmatch(v):
            blocks.append(f"{n} has a version that is not a version")
            continue
        if n in old_versions and v not in old_versions[n]:
            blocks.append(f"a second copy of {n} at another version would be added")
        if entry.get("inBundle") is not True and not _fetched(entry):
            blocks.append(f"{n} is not from the registry with a sha512")
    top = {key_name(k): e for k, e in new_entries.items() if k == f"node_modules/{key_name(k)}"}
    for r in requested:
        e = top.get(r["name"])
        if e is None:
            blocks.append(f"{r['name']} is not a top-level package of the candidate")
        elif r["version"] is not None and e.get("version") != r["version"]:
            blocks.append(f"{r['name']} is not locked at the requested version")
    return {"blocks": _dedupe(blocks), "new": new_entries, "changed": sorted(changed), "removed": sorted(removed)}


def _dedupe(items):
    seen, out = set(), []
    for i in items:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


# ---- the registry's facts -----------------------------------------------------------------------------------------------

def _when(value):
    """A datetime for an ISO time string of the registry's shape, else None."""
    if not isinstance(value, str) or not TIME.fullmatch(value):
        return None
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return None


def _license(value):
    if isinstance(value, dict):
        value = value.get("type")
    return value if isinstance(value, str) and LICENSE.fullmatch(value) else None


def permissive(lic):
    """True when every SPDX token of a license string is in the common permissive set (`(MIT OR Apache-2.0)` is; an unknown token is not)."""
    if lic is None:
        return False
    tokens = [t for t in re.split(r"[()\s]+", lic) if t and t not in ("OR", "AND")]
    return bool(tokens) and all(t in PERMISSIVE for t in tokens)


def facts(view, version, now, lim=None):
    """The facts of one package version from the parsed `npm view NAME@VERSION --json` (the full manifest with `time` and `maintainers`), or None
    values where the registry did not give one in the expected shape. `age_days` is from time[version], never from any other field."""
    lim = lim or DEFAULTS
    v = view if isinstance(view, dict) else {}
    time = v.get("time") if isinstance(v.get("time"), dict) else {}
    published, created = _when(time.get(version)), _when(time.get("created"))
    dist = v.get("dist") if isinstance(v.get("dist"), dict) else {}
    size = dist.get("unpackedSize")
    maint = v.get("maintainers")
    return {
        "published": published.strftime("%Y-%m-%dT%H:%M:%SZ") if published else None,
        "age_days": (now - published).days if published else None,
        "created_days": (now - created).days if created else None,
        "license": _license(v.get("license")),
        "deprecated": bool(v.get("deprecated")),
        "unpacked_size": size if isinstance(size, int) and not isinstance(size, bool) and 0 <= size <= SIZE_MAX else None,
        "maintainers": min(len(maint), MAINTAINERS_MAX) if isinstance(maint, list) else None,
    }


def parse_view(text):
    """The parsed `npm view --json` output, or None when it is not one JSON object (an unpublished version prints nothing, a missing package gives
    an error: both are no record). A duplicate key is not a record."""
    if not isinstance(text, str) or not text.strip() or len(text) > 5_000_000:
        return None
    try:
        v = json.loads(text, object_pairs_hook=_no_dupes)
    except ValueError:
        return None
    return v if isinstance(v, dict) else None


def _no_dupes(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise ValueError("duplicate key")
        out[k] = v
    return out


# ---- the report -------------------------------------------------------------------------------------------------------

def lock_sha(text):
    """The sha256 (64 hex) of the candidate lock's bytes: what the second confirm names and what the build re-hashes."""
    return hashlib.sha256(text.encode("utf-8") if isinstance(text, str) else text).hexdigest()


def build_report(requested, old, new, views, now, lim=None):
    """The report of a candidate: {"status": "OK"|"REFUSED", "blocks": [..], "warns": [..], "packages": [..], "totals": {..}}.
    `views` maps "name@version" to the parsed `npm view` of each new package (absent or None: no registry record). Every package of the candidate
    that is new is judged, not only the requested ones: a fresh release as a transitive is where harm would land. The age is from time[version];
    a missing time is a block; a package younger than min_age_days is a block; and the other facts are warnings the human weighs."""
    lim = {**DEFAULTS, **(lim or {})}
    a = analyse(old, new, requested)
    blocks, warns, packages = list(a["blocks"]), [], []
    entries = a["new"]
    if len(entries) > lim["max_new"]:
        blocks.append(f"{len(entries)} new packages: more than {lim['max_new']}")
    direct_names = {r["name"] for r in requested}
    for key in sorted(entries, key=lambda k: (key_name(k) or "", k)):
        entry, n = entries[key], key_name(key)
        v = entry.get("version")
        if n is None or not isinstance(v, str) or not LOCK_VERSION.fullmatch(v):
            continue
        view = (views or {}).get(f"{n}@{v}")
        f = facts(view, v, now, lim)
        direct = key == f"node_modules/{n}" and n in direct_names
        packages.append({"name": n, "version": v, "direct": direct, "has_install_script": entry.get("hasInstallScript") is True, **f})
        label = f"{n}@{v}"
        if view is None or not isinstance(view, dict):
            blocks.append(f"{label} has no registry record")
            continue
        if f["age_days"] is None:
            blocks.append(f"{label} has no publish time: its age is unknown")
        elif f["age_days"] < lim["min_age_days"]:
            blocks.append(f"{label} is {f['age_days']} days old: younger than {lim['min_age_days']}")
        if f["deprecated"]:
            warns.append(f"{label} is deprecated")
        if packages[-1]["has_install_script"]:
            warns.append(f"{label} has an install script: it never runs here, so the package may not work")
        if f["license"] is None:
            warns.append(f"{label} has a license that cannot be read")
        elif not permissive(f["license"]):
            warns.append(f"{label} has the license {f['license']}, not a common permissive one")
        if f["created_days"] is not None and f["created_days"] < lim["new_package_days"]:
            warns.append(f"{n} was first published {f['created_days']} days ago")
    return {"status": "REFUSED" if blocks else "OK", "blocks": _dedupe(blocks), "warns": _dedupe(warns), "packages": packages,
            "totals": {"new": len(entries), "direct": sum(1 for p in packages if p["direct"]), "changed": len(a["changed"]),
                       "removed": len(a["removed"])}}


# ---- the name of the new environment -----------------------------------------------------------------------------------

def next_env_name(base, taken):
    """(name, problem): `BASE_upN` for the smallest N from 1 that is not in `taken` (every name in environments/, the config, the pin files and the
    names reserved by live env jobs, computed by the caller), after removing a trailing `_upN` from `base`. The name fits the environment shape and
    ENV_NAME_MAX characters, else a problem, never a cut name."""
    if not isinstance(base, str) or not ENV_NAME.fullmatch(base):
        return None, "the base is not an environment name"
    stem = UP_SUFFIX.sub("", base)
    taken = set(taken or ())
    for n in range(1, UP_MAX + 1):
        name = f"{stem}_up{n}"
        if len(name) > ENV_NAME_MAX or not ENV_NAME.fullmatch(name):
            return None, f"{name} is longer than {ENV_NAME_MAX} characters"
        if name not in taken:
            return name, None
    return None, f"no free number up to {UP_MAX} for {stem}"


def now_utc():
    return datetime.now(timezone.utc)
