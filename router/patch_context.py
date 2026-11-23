"""SPEC_READER_CONTEXT: the files a patch leans on, for the patch readers.

A patch reader sees the diff, so a claim about code outside the diff cannot be checked (NEXUS-lite: three false `blocker`s in 16 issues). This module builds one more DATA
section for the reader's bundle: the content, at the job's base commit, of (1) the files the patch modifies and (2) the repository files its added lines import. Read with git at
that commit, never from a working tree; bounded and visibly cut; never an error: any failure gives an empty context (the bundle is then byte-identical to the one without this module).
These files go to two external model providers, so a file that looks like a secret is never shown (EXCLUDED, SECRET_TEXT)."""
import hashlib
import posixpath
import re

from acceptance import intake
from router import protected_files

MAX_FILES = 6
MAX_TOTAL = 24_000                 # bytes of file text over all files
MAX_FILE = 8_000                   # bytes of one file before it is cut at a line boundary
MAX_BLOB = 200_000                 # a blob larger than this is not read at all
MAX_LISTED = 10                    # paths named in the "not shown" line
MAX_CANDIDATES = 50                # files looked at before the rest is only counted
MAX_LINE = 1_000                   # an added line longer than this is not scanned for imports
REGULAR = (b"100644", b"100755")   # a symlink (120000) or a submodule (160000) is never a context file
JS_EXT = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")
PROBE = ("",) + JS_EXT
COMMIT = re.compile(r"[0-9a-f]{40}")
LS_LINE = re.compile(rb"^(\d{6}) (\w+) ([0-9a-f]{40}) +(\d+|-)\t(.+)$", re.S)
EXCLUDED = re.compile(r"(^|/)\.env|(^|/)id_(rsa|dsa|ecdsa|ed25519)|(^|/)\.(npmrc|pypirc|netrc|git-credentials)$|\.(pem|key|p12|pfx|jks|keystore|tfstate)$"
                      r"|(^|/)(secrets?|credentials?)(\.|/|$)|(^|/)node_modules/|(^|/)(package-lock\.json|yarn\.lock|pnpm-lock\.yaml)$|\.lock$|\.min\.", re.I)
SECRET_TEXT = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----|\bAKIA[0-9A-Z]{16}\b|\bsk-[A-Za-z0-9_-]{20,}")
JS_IMPORT = (re.compile(r"""\bfrom\s+['"]([^'"\n]+)['"]"""), re.compile(r"""\bimport\s*\(\s*['"]([^'"\n]+)['"]\s*\)"""),
             re.compile(r"""\brequire\s*\(\s*['"]([^'"\n]+)['"]\s*\)"""), re.compile(r"""\bimport\s+['"]([^'"\n]+)['"]"""))
PY_FROM_REL = re.compile(r"^\s*from\s+(\.+)([A-Za-z_][\w.]*)?\s+import\b")
PY_FROM = re.compile(r"^\s*from\s+([A-Za-z_][\w.]*)\s+import\b")
PY_IMPORT = re.compile(r"^\s*import\s+([A-Za-z_][\w.,\s]*)")
HUNK = re.compile(r"^@@ -\d+(?:,(\d+))? \+\d+(?:,(\d+))? @@")


def tracked(repo, commit):
    """{path: (blob sha, size)} of the regular files of the commit's tree."""
    if not isinstance(commit, str) or not COMMIT.fullmatch(commit):
        raise ValueError("the commit is a 40-digit hex sha")       # a job's commit is frozen at creation; anything else (an option, a ref name) is never given to git
    out = intake.git(repo, "ls-tree", "-r", "-z", "-l", "--full-tree", commit, clean=True)
    files = {}
    for entry in out.split(b"\0"):
        m = LS_LINE.match(entry) if entry else None
        if m and m.group(2) == b"blob" and m.group(1) in REGULAR:
            try:
                files[m.group(5).decode("utf-8")] = (m.group(3).decode(), int(m.group(4)))
            except (UnicodeDecodeError, ValueError):
                continue
    return files


def _name(rest):
    """The path of a `--- ` or `+++ ` header after its `a/` or `b/`, or None (/dev/null, a quoted name with special bytes, another form). git appends a tab to a name with a space."""
    rest = rest.rstrip("\t")
    if rest.startswith('"') or not (rest.startswith("a/") or rest.startswith("b/")):
        return None
    return rest[2:] or None


def parse_patch(text):
    """(modified paths in diff order, {path: [added lines]}, how many file names could not be read). A file the patch creates or deletes is not "modified". Hunks are followed by their
    line counts, so a line inside a hunk that looks like a header (`--- a/x`, `+++ b/x`) is a hunk line; lines are split on newlines only."""
    modified, added, unread = [], {}, 0
    old = current = None
    left_old = left_new = 0
    for line in text.split("\n"):
        line = line[:-1] if line.endswith("\r") else line
        if left_old > 0 or left_new > 0:                                   # inside a hunk: its counts say how many lines are still its own
            if line.startswith("+"):
                left_new -= 1
                if current is not None:
                    added.setdefault(current, []).append(line[1:])
            elif line.startswith("-"):
                left_old -= 1
            elif line.startswith("\\"):
                pass
            else:                                                          # a context line (a space, or an empty line some tools strip it to)
                left_old -= 1
                left_new -= 1
            continue
        m = HUNK.match(line)
        if m:
            left_old = int(m.group(1)) if m.group(1) is not None else 1
            left_new = int(m.group(2)) if m.group(2) is not None else 1
        elif line.startswith("--- "):
            old = _name(line[4:])
            if old is None and not line[4:].startswith("/dev/null"):
                unread += 1
            current = None
        elif line.startswith("+++ "):
            current = _name(line[4:])
            if current is None and not line[4:].startswith("/dev/null"):
                unread += 1
            if current is not None and old == current and current not in modified:
                modified.append(current)
            old = None
    return modified, added, unread


def _inside(path):
    """The normalised repository-relative path, or None when it leaves the repository or is absolute."""
    if not path or path.startswith("/") or "\0" in path:
        return None
    norm = posixpath.normpath(path)
    return None if norm == ".." or norm.startswith("../") or norm == "." else norm


def _js_candidates(source, spec):
    if spec.startswith("@/"):
        base = _inside("src/" + spec[2:])
    elif spec.startswith("./") or spec.startswith("../"):
        base = _inside(posixpath.join(posixpath.dirname(source), spec))
    else:
        return []
    if base is None:
        return []
    return [base + ext for ext in PROBE] + [f"{base}/index{ext}" for ext in JS_EXT]


def _py_candidates(source, module, dots=0):
    if dots:
        up = posixpath.dirname(source)
        for _ in range(dots - 1):
            if not up:
                return []                                                   # the dots climb past the repository root
            up = posixpath.dirname(up)
        if not module:
            return [posixpath.join(up, "__init__.py")] if up else ["__init__.py"]
        base = _inside(posixpath.join(up, *module.split(".")))
    else:
        base = _inside(posixpath.join(*module.split(".")))
    if base is None:
        return []
    return [base + ".py", f"{base}/__init__.py"]


def imports(source, lines):
    """The candidate paths (probe order, before checking the tree) the added lines of `source` import, in order of first appearance. A very long line is not scanned."""
    found = []
    lines = [l for l in lines if len(l) <= MAX_LINE]
    if source.endswith(JS_EXT):
        for line in lines:
            for rx in JS_IMPORT:
                for m in rx.finditer(line):
                    found.append(_js_candidates(source, m.group(1)))
    elif source.endswith(".py"):
        for line in lines:
            m = PY_FROM_REL.match(line)
            if m:
                found.append(_py_candidates(source, m.group(2) or "", len(m.group(1))))
                continue
            m = PY_FROM.match(line)
            if m:
                found.append(_py_candidates(source, m.group(1)))
                continue
            m = PY_IMPORT.match(line)
            if m:
                for name in m.group(1).split(","):
                    parts = name.split()
                    if parts:
                        found.append(_py_candidates(source, parts[0]))
    return found


def _cut(text):
    """(shown text, bytes not shown): at most MAX_FILE bytes, cut at a line boundary (a text with no line break in its first MAX_FILE bytes is cut where it is, and ends with one)."""
    raw = text.encode("utf-8")
    if len(raw) <= MAX_FILE:
        return text, 0
    head = raw[:MAX_FILE].decode("utf-8", "ignore")             # a multi-byte character split at the limit is dropped, not guessed
    if "\n" in head:
        head = head[:head.rindex("\n") + 1]
    return (head if head.endswith("\n") else head + "\n"), len(raw) - len(head.encode("utf-8"))


def _candidates(repo, commit, patch, protected=()):
    """(paths to show in order, tree, how many names were left out). Order: the files the patch modifies; then the files its added lines import that the agent could have written (not
    on the repository's protected list); then the imported files on that list (the scaffold: fixed, and never the place a false claim about the patch's own work hides). Within a
    group, order of first appearance."""
    modified, added, unread = parse_patch(patch)
    files = tracked(repo, commit)
    first, open_, fixed, seen = [], [], [], set()
    for path in modified:
        if path in files and path not in seen:
            first.append(path)
            seen.add(path)
    for source in list(added):
        for cands in imports(source, added[source]):
            hit = next((c for c in cands if c in files), None)       # the first candidate of the probe order that is a tracked regular file
            if hit is not None and hit not in seen and hit not in added:
                (fixed if protected and protected_files.match_of(hit, list(protected)) else open_).append(hit)
                seen.add(hit)
    ordered = first + open_ + fixed
    return [p for p in ordered if not EXCLUDED.search(p)], files, unread + sum(1 for p in ordered if EXCLUDED.search(p))


def build(repo, commit, patch, protected=()):
    """(section text or "", info). `info`: {"shown": [[path, bytes]], "not_shown": [paths, at most MAX_LISTED], "not_shown_total": n, "skipped": n (excluded, unreadable, secret-looking,
    names git quoted), "sha256": of the section text or None} - the ledger line; `failed` (the type of the error, never its text) when anything went wrong. Never raises. When every
    candidate is dropped by a cap the section is empty and the names are in the ledger only."""
    try:
        order, files, skipped = _candidates(repo, commit, patch, protected)
        shown, not_shown, parts, total = [], [], [], 0
        for n_seen, path in enumerate(order):
            sha, size = files[path]
            if n_seen >= MAX_CANDIDATES or len(shown) >= MAX_FILES or total >= MAX_TOTAL or size > MAX_BLOB:
                not_shown.append(path)
                continue
            try:
                raw = intake.git(repo, "cat-file", "blob", sha, clean=True)
                if b"\0" in raw:
                    skipped += 1
                    continue
                text = raw.decode("utf-8")
            except (UnicodeDecodeError, intake.IntakeError):
                skipped += 1
                continue
            if SECRET_TEXT.search(text):
                skipped += 1
                continue
            body, rest = _cut(text.replace("\r\n", "\n"))
            piece = body + (f"[cut: {rest} more bytes not shown]\n" if rest else "")
            n = len(piece.encode("utf-8"))
            if total + n > MAX_TOTAL:
                not_shown.append(path)
                continue
            total += n
            shown.append([path, n])
            parts.append(f"file: {path}\n{piece.rstrip(chr(10))}")
        info = {"shown": shown, "not_shown": not_shown[:MAX_LISTED], "not_shown_total": len(not_shown), "skipped": skipped, "sha256": None}
        if not parts:
            return "", info
        if not_shown:
            more = len(not_shown) - MAX_LISTED
            parts.append("[not shown: " + ", ".join(not_shown[:MAX_LISTED]) + (f" (and {more} more)" if more > 0 else "") + "]")
        section = "\n\n".join(parts)
        info["sha256"] = hashlib.sha256(section.encode("utf-8")).hexdigest()
        return section, info
    except Exception as e:                                     # noqa: BLE001 - by design: nothing here may stop a reading
        return "", {"shown": [], "not_shown": [], "not_shown_total": 0, "skipped": 0, "sha256": None, "failed": type(e).__name__}
