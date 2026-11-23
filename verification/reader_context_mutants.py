"""Mutants for SPEC_READER_CONTEXT (router/patch_context.py and its wiring): each applied alone in a worktree; killed = a test FAILED and pytest reported no error.
The list is the reviewer's (Opus, 2026-11-23) plus mine, cut to the ones that can be written as a single edit. Usage: <this> <worktree> <python> [name fragments]."""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
ONLY = sys.argv[3:]
PC, PR, PRR = "router/patch_context.py", "router/patch_read.py", "router/patch_read_run.py"
T = ["-rfEs", "tests/test_patch_context.py", "tests/test_patch_read_run.py"]
M = [
    # ranking and choice
    ("ranking: the protected group before the open one", PC, [("ordered = first + open_ + fixed", "ordered = first + fixed + open_")]),
    ("ranking: imports before the modified files", PC, [("ordered = first + open_ + fixed", "ordered = open_ + first + fixed")]),
    ("ranking: no protected group at all", PC, [("(fixed if protected and protected_files", "(fixed if False and protected_files")]),
    ("a created file is shown again", PC, [("if hit is not None and hit not in seen and hit not in added:", "if hit is not None and hit not in seen:")]),
    ("no dedup of imports", PC, [("if hit is not None and hit not in seen and hit not in added:", "if hit is not None and hit not in added:")]),
    ("the last probe candidate wins", PC, [("hit = next((c for c in cands if c in files), None)", "hit = next((c for c in reversed(cands) if c in files), None)")]),
    ("a modified path need not be tracked", PC, [("if path in files and path not in seen:", "if path not in seen:")]),
    # caps
    ("file cap off by one", PC, [("len(shown) >= MAX_FILES", "len(shown) > MAX_FILES")]),
    ("seven files", PC, [("MAX_FILES = 6", "MAX_FILES = 7")]),
    ("blob cap off by one", PC, [("or size > MAX_BLOB:", "or size >= MAX_BLOB:")]),
    ("no blob cap", PC, [(" or size > MAX_BLOB:", ":")]),
    ("total cap off by one", PC, [("if total + n > MAX_TOTAL:", "if total + n >= MAX_TOTAL:")]),
    ("no total cap", PC, [("if total + n > MAX_TOTAL:", "if False:")]),
    ("files are read after the total is full", PC, [(" or total >= MAX_TOTAL or size", " or size")]),
    ("the not-shown line is never written", PC, [("        if not_shown:\n            more =", "        if False:\n            more =")]),
    ("every not-shown path is listed", PC, [('", ".join(not_shown[:MAX_LISTED])', '", ".join(not_shown)')]),
    ("no 'and N more'", PC, [('(f" (and {more} more)" if more > 0 else "")', '""')]),
    # the cut
    ("a file of exactly the limit is cut", PC, [("if len(raw) <= MAX_FILE:", "if len(raw) < MAX_FILE:")]),
    ("no line boundary", PC, [('        head = head[:head.rindex("\\n") + 1]', "        pass")]),
    ("the boundary drops the newline", PC, [('head[:head.rindex("\\n") + 1]', 'head[:head.rindex("\\n")]')]),
    ("characters instead of bytes", PC, [('len(raw) - len(head.encode("utf-8"))', "len(raw) - len(head)")]),
    ("a split character raises", PC, [('.decode("utf-8", "ignore")', '.decode("utf-8")')]),
    ("no cut marker", PC, [('(f"[cut: {rest} more bytes not shown]\\n" if rest else "")', '""')]),
    ("the cut line has no break before the marker", PC, [('return (head if head.endswith("\\n") else head + "\\n"),', "return head,")]),
    ("CRLF kept", PC, [('_cut(text.replace("\\r\\n", "\\n"))', "_cut(text)")]),
    # what is never shown
    ("no .env exclusion", PC, [('r"(^|/)\\.env|(^|/)id_', 'r"(^|/)id_')]),
    ("no id_rsa exclusion", PC, [("|(^|/)id_(rsa|dsa|ecdsa|ed25519)", "")]),
    ("no .pem or .key exclusion", PC, [("\\.(pem|key|p12|pfx|jks|keystore|tfstate)$", "\\.(p12|pfx|jks|keystore|tfstate)$")]),
    ("no secrets or credentials exclusion", PC, [("|(^|/)(secrets?|credentials?)(\\.|/|$)", "")]),
    ("no node_modules exclusion", PC, [("|(^|/)node_modules/", "")]),
    ("no lock exclusion", PC, [("|\\.lock$", "")]),
    ("no minified exclusion", PC, [('|\\.min\\.", re.I)', '", re.I)')]),
    ("exclusions are case sensitive", PC, [(", re.I)\nSECRET_TEXT", ")\nSECRET_TEXT")]),
    ("no check of the text for a key", PC, [("if SECRET_TEXT.search(text):", "if False:")]),
    ("a NUL byte is shown", PC, [('if b"\\0" in raw:', "if False:")]),
    ("a bad UTF-8 file is shown with replacements", PC, [('text = raw.decode("utf-8")', 'text = raw.decode("utf-8", "replace")')]),
    ("a symlink is a regular file", PC, [('REGULAR = (b"100644", b"100755")', 'REGULAR = (b"100644", b"100755", b"120000")')]),
    ("the entry type is not checked", PC, [('if m and m.group(2) == b"blob" and m.group(1) in REGULAR:', "if m and m.group(1) in REGULAR + (b'120000',):")]),
    ("the skipped count is zero", PC, [('"skipped": skipped, "sha256": None}', '"skipped": 0, "sha256": None}')]),
    # the commit and the path
    ("the commit is matched, not fully matched", PC, [("COMMIT.fullmatch(commit)", "COMMIT.match(commit)")]),
    ("no check of the commit", PC, [("if not isinstance(commit, str) or not COMMIT.fullmatch(commit):", "if False:")]),
    ("an upper-case commit is accepted", PC, [('COMMIT = re.compile(r"[0-9a-f]{40}")', 'COMMIT = re.compile(r"[0-9a-fA-F]{40}")')]),
    ("the content is read from the working tree", PC, [('raw = intake.git(repo, "cat-file", "blob", sha, clean=True)', 'raw = __import__("pathlib").Path(str(repo), path).read_bytes()')]),
    ("an absolute path is inside", PC, [('if not path or path.startswith("/") or "\\0" in path:', 'if not path or "\\0" in path:')]),
    ("a path may leave the repository", PC, [('return None if norm == ".." or norm.startswith("../") or norm == "." else norm', 'return None if norm == "." else norm')]),
    ("no normalisation of a path", PC, [("norm = posixpath.normpath(path)", "norm = path")]),
    # the imports
    ("extension before the bare path", PC, [('PROBE = ("",) + JS_EXT', 'PROBE = JS_EXT + ("",)')]),
    ("no bare path in the probe", PC, [('PROBE = ("",) + JS_EXT', "PROBE = JS_EXT")]),
    ("index before the extension", PC, [('return [base + ext for ext in PROBE] + [f"{base}/index{ext}" for ext in JS_EXT]', 'return [f"{base}/index{ext}" for ext in JS_EXT] + [base + ext for ext in PROBE]')]),
    ("the alias goes to the root", PC, [('base = _inside("src/" + spec[2:])', "base = _inside(spec[2:])")]),
    ("a package name is relative", PC, [('    elif spec.startswith("./") or spec.startswith("../"):', "    elif True:")]),
    ("relative to the root, not to the file", PC, [("base = _inside(posixpath.join(posixpath.dirname(source), spec))", "base = _inside(spec)")]),
    ("python dots off by one", PC, [("for _ in range(dots - 1):", "for _ in range(dots):")]),
    ("python dots past the root are followed", PC, [("            if not up:\n                return []", "            if False:\n                return []")]),
    ("no package init candidate", PC, [('return [base + ".py", f"{base}/__init__.py"]', 'return [base + ".py"]')]),
    ("an 'as' alias stays in the name", PC, [("found.append(_py_candidates(source, parts[0]))", "found.append(_py_candidates(source, name.strip()))")]),
    ("a long line is scanned", PC, [("lines = [l for l in lines if len(l) <= MAX_LINE]", "lines = list(lines)")]),
    # the patch
    ("lines are split like splitlines", PC, [('for line in text.split("\\n"):', "for line in text.splitlines():")]),
    ("hunk counts are not followed", PC, [("if left_old > 0 or left_new > 0:", "if False:")]),
    ("an added line keeps its plus", PC, [("added.setdefault(current, []).append(line[1:])", "added.setdefault(current, []).append(line)")]),
    ("a created file counts as modified", PC, [("if current is not None and old == current and current not in modified:", "if current is not None and current not in modified:")]),
    ("the old name is never reset", PC, [("            old = None\n    return modified", "            pass\n    return modified")]),
    ("a tab after a name is kept", PC, [('rest = rest.rstrip("\\t")', "pass")]),
    ("CRLF in a patch is kept", PC, [('line = line[:-1] if line.endswith("\\r") else line', "line = line")]),
    ("an unreadable name is not counted", PC, [('            if current is None and not line[4:].startswith("/dev/null"):\n                unread += 1', "            pass")]),
    # failure and ledger
    ("a failure raises", PC, [('return "", {"shown": [], "not_shown": [], "not_shown_total": 0, "skipped": 0, "sha256": None, "failed": type(e).__name__}', "raise")]),
    ("a failure carries its text", PC, [('"failed": type(e).__name__}', '"failed": str(e)}')]),
    ("the ledger sha is of something else", PC, [('info["sha256"] = hashlib.sha256(section.encode("utf-8")).hexdigest()', 'info["sha256"] = hashlib.sha256(parts[0].encode("utf-8")).hexdigest()')]),
    ("no ledger line", PRR, [('log.emit("patch_context", sha12=sha[:12], **cinfo)', "pass")]),
    ("the ledger carries the text", PRR, [('log.emit("patch_context", sha12=sha[:12], **cinfo)', 'log.emit("patch_context", sha12=sha[:12], section=text, **cinfo)')]),
    ("the summary hides a failure", PRR, [('summary["context_failed"] = cinfo["failed"]', "pass")]),
    ("no marker for a job without a repository", PRR, [(', "sha256": None, "absent": "no repo or commit in the job inputs"})', ', "sha256": None})')]),
    ("the base commit is not the job's", PRR, [('repo, commit = inputs.get("repo"), inputs.get("commit")', 'repo, commit = inputs.get("repo"), "HEAD"')]),
    ("the protected list is not passed", PRR, [("pc.build(repo, commit, text, globs)", "pc.build(repo, commit, text)")]),
    ("the bundle ignores the context", PRR, [("passing examples do not prove the patch is clean\", text, context), sid, sha", "passing examples do not prove the patch is clean\", text), sid, sha")]),
    # the render
    ("the context is not indented", PR, [('"=== DATA " + HEADER_CONTEXT + " ===", ind(context)]', '"=== DATA " + HEADER_CONTEXT + " ===", context]')]),
    ("the header does not say BEFORE", PR, [("as they were BEFORE the patch;", "as they were;")]),
    ("an empty context adds a header", PR, [("    if context:\n        parts +=", "    if context is not None:\n        parts +=")]),
]

if __name__ == "__main__":
    killed = ran = 0
    for name, F, edits in M:
        if ONLY and not any(o in name for o in ONLY):
            continue
        p = WT / F
        orig = p.read_text()
        text = orig
        stale = [a[:70] for a, _ in edits if text.count(a) != 1]
        if stale:
            print(f"STALE   {name}: {stale}", flush=True)
            continue
        for a, b in edits:
            text = text.replace(a, b, 1)
        p.write_text(text)
        ran += 1
        try:
            r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *T], cwd=WT, capture_output=True, text=True, timeout=600)
        finally:
            p.write_text(orig)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        fails = [line for line in r.stdout.splitlines() if line.startswith("FAILED tests/test_")][:1]
        k = bool(fails) and "error" not in last
        killed += k
        print(f"{'KILLED ' if k else 'ERROR  ' if 'error' in last else 'SURVIVED'} {name}: {fails or last}", flush=True)
    print(f"RESULT: {killed}/{ran} killed")
