"""SPEC_PRD_REFS: reference repositories for the PRD writer (`argus prd new --ref NAME`).

The README.md and the list of tracked paths of a registered repository, read from its HEAD commit through git, kept in the job (frozen) and shown to the writer as DATA in
its prompt, so a request like "the same figures as ledger-cli" can be written from what ledger-cli says. Nothing else is read, nothing is written, copied into the sandbox
or given to a tool: the text only ever goes into the writer's user prompt. Everything here is bounded and filtered the way the human's own messages are (no control or
format character, no way to close the data block)."""
import re
import unicodedata
from pathlib import Path

from acceptance import intake
from codetask import prd_writer as pw
from router import issue as ri
from router import job as rj

MAX_REFS = 2
README_MAX = 8000                 # characters kept of README.md (after filtering and escaping)
README_BYTES = 1 << 20            # a larger blob is refused before it is read
FILES_MAX = 200                   # paths listed
FILES_CHARS = 6000                # characters of the list
PATH_MAX = 200
BLOCK_BUDGET = 0.25               # share of the writer's max_input_tokens the rendered references may take
CHARS_PER_TOKEN = 3               # the heuristic of the gateway's check (config.yaml, prd_writer max_input_tokens)
CUT = "[cut]"
LS_LINE = re.compile(rb"^(\d{6}) (\w+) ([0-9a-f]{40}) +(\d+|-)\t(.+)$", re.S)


def _bad(why):
    raise rj.Refused(f"reference repository: {why}; nothing was started")


def clean_text(text):
    """Control and format characters (but newline and tab) become `?`; a run of three or more `<` or `>` is spread so that `<<<` and `>>>` cannot occur."""
    out = "".join("?" if (c not in "\n\t" and (unicodedata.category(c)[0] == "C" or unicodedata.category(c) in ("Zl", "Zp"))) else c for c in text)
    out = re.sub(r"<{3,}", lambda m: " ".join(m.group()), out)
    return re.sub(r">{3,}", lambda m: " ".join(m.group()), out)


def _paths(path, commit):
    raw = intake.git(path, "ls-tree", "-r", "-z", "--name-only", commit, clean=True).split(b"\0")
    names = [clean_text(p.decode("utf-8", errors="backslashreplace").replace("\n", "\\n"))[:PATH_MAX] for p in raw if p]
    shown, used = [], 0
    for n in names[:FILES_MAX]:
        if used + len(n) + 1 > FILES_CHARS:
            break
        shown.append(n)
        used += len(n) + 1
    more = len(names) - len(shown)
    return "\n".join(shown) + (f"\n(and {more} more)" if more else "")


def _readme(path, commit):
    """README.md of the commit's root as text, or None (absent, a symlink, a submodule): only a regular blob counts."""
    out = intake.git(path, "ls-tree", "-z", "-l", commit, "--", "README.md", clean=True)
    entry = next((e for e in out.split(b"\0") if e), None)
    m = LS_LINE.match(entry) if entry else None
    if not m or m.group(5) != b"README.md" or m.group(2) != b"blob" or m.group(1) not in (b"100644", b"100755"):
        return None
    if int(m.group(4)) > README_BYTES:
        _bad("README.md is over 1 MiB")
    try:
        text = intake.git(path, "cat-file", "blob", m.group(3).decode(), clean=True).decode("utf-8-sig")
    except UnicodeDecodeError:
        _bad("README.md is not UTF-8 text")
    text = clean_text(text.replace("\r\n", "\n").replace("\r", "\n"))
    return text if len(text) <= README_MAX else text[:README_MAX] + CUT


def read(cfg, name, *, target):
    """{name, commit, files, readme} of the registered repository `name` at its HEAD (target: the PRD's own repository name). Refused, nothing made, on anything unexpected."""
    path, _env = ri.repo_of(cfg, name)
    tpath, _ = ri.repo_of(cfg, target)
    if name == target or Path(path).resolve() == Path(tpath).resolve():
        _bad(f"{name} is the repository the PRD is for")
    try:
        commit = intake.git(path, "rev-parse", "--verify", "HEAD^{commit}", clean=True).decode().strip()
        files, readme = _paths(path, commit), _readme(path, commit)
    except (intake.IntakeError, OSError, ValueError) as e:
        _bad(f"{name}: {e}")
    if not files and readme is None:
        _bad(f"{name} has neither files nor a README.md")
    return {"name": name, "commit": commit, "files": files, "readme": readme}


def read_all(cfg, names, *, target):
    names = list(names or ())
    if len(names) > MAX_REFS or len(set(names)) != len(names):
        _bad(f"at most {MAX_REFS} different --ref")
    refs = [read(cfg, n, target=target) for n in names]
    limit = int(BLOCK_BUDGET * int(ri._settings(cfg).get("max_input_tokens", 0) or _writer_input_tokens(cfg)) * CHARS_PER_TOKEN)
    if refs and sum(len(block(r)) for r in refs) > limit:
        _bad(f"the references are over {limit} characters, a quarter of the writer's input")
    return refs


def _writer_input_tokens(cfg):
    return int(((cfg.get("prd_writer") or {}).get("turn") or {}).get("max_input_tokens", 40000))


block = pw.ref_block


def valid(refs):
    """The shape job.json holds (absent is fine): a list of at most MAX_REFS dicts of text."""
    return refs is None or (isinstance(refs, list) and len(refs) <= MAX_REFS and all(
        isinstance(r, dict) and all(isinstance(r.get(k), str) for k in ("name", "commit", "files")) and
        (r.get("readme") is None or isinstance(r.get("readme"), str)) for r in refs))
