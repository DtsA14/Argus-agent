"""SPEC_PRD_STAGE (part B1 of SPEC_PRD_QUEUE): a PRD folder is checked against the data paths that pass through Argus, then approved once.

  argus prd check <dir>                 read only, no model, no money: BLOCK and WARN findings, and the sha of what was read
  argus prd approve <dir> --sha <sha>   the same check on the same bytes, then `queue.new` (a PENDING queue; the money is still `queue go`)

The folder is read ONCE into memory (no symlink, regular files only, fixed names, size caps) and the findings, the sha and the queue all use those bytes.
The checks import the running code (router.stage_viewer.API, router.stage_data's tables), never a copy of them.
"""
import hashlib
import json
import os
import re
import stat
from pathlib import Path

from . import job as rj
from . import queue as rq
from . import stage_data as sd
from . import stage_viewer as sv

BLOCK, WARN = "BLOCK", "WARN"
DOC_MAX = 200_000
TABLES = {"JOB_FIELDS": sd.JOB_FIELDS, "STAGE_FIELDS": sd.STAGE_FIELDS, "LOG_FIELDS": sd.LOG_FIELDS}
# names the snapshot publishes for a job that are not in JOB_FIELDS (router/stage_data.py project_job): the title is derived, stages and log are nested
PUBLISHED_EXTRA = {"JOB_FIELDS": {"title", "stages", "log"}}
TOP_KEYS, ITEM_KEYS, PATH_KEYS = {"repo", "commit", "max_usd", "items"}, {"n", "paths", "fields"}, {"side", "path", "via_proxy"}
SIDES = ("viewer-api", "ledger")
PLAIN = re.compile(r"[\x21-\x7e]+")
LEFT = r"(?<![A-Za-z_.@~\\-])"
API_HIT = re.compile(LEFT + r"/api/[A-Za-z0-9_./?=&-]*")
VERB_HIT = re.compile(r"\b(?:GET|HEAD|POST|PUT|PATCH|DELETE)\s+(/[A-Za-z0-9_./?=&-]*)")
TAIL = ".,;:)?]'\""


class Folder(Exception):
    pass


def _read(dir_, name, cap):
    """One regular file of the folder, as bytes, without following a link; at most `cap` bytes."""
    try:
        fd = os.open(os.path.join(dir_, name), os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)         # a FIFO must not hang the read; fstat refuses it
    except OSError as e:
        raise Folder(f"{name}: cannot be read ({e.strerror})") from None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise Folder(f"{name}: is not a regular file")
        data = os.read(fd, cap + 1)
        if len(data) > cap:
            raise Folder(f"{name}: is larger than {cap} bytes")
        return data
    finally:
        os.close(fd)


def read_folder(dir_):
    """{name: bytes} of PRD.md, issues.json and issue-1.md ... issue-N.md (N = the items of issues.json), read once; Folder if anything else is there or is wrong."""
    try:
        names = sorted(os.listdir(dir_))
    except OSError as e:
        raise Folder(f"{dir_}: cannot be listed ({e.strerror})") from None
    files = {"PRD.md": _read(dir_, "PRD.md", DOC_MAX), "issues.json": _read(dir_, "issues.json", DOC_MAX)}
    try:
        n = len(json.loads(files["issues.json"].decode("utf-8"))["items"])
    except (ValueError, KeyError, TypeError, AttributeError, RecursionError):
        raise Folder("issues.json: is not valid UTF-8 JSON with a list \"items\"") from None
    expected = {"PRD.md", "issues.json", *(f"issue-{k}.md" for k in range(1, n + 1))}
    extra = sorted(set(names) - expected)
    if extra:
        raise Folder(f"unexpected entries in the folder: {', '.join(ascii(e) for e in extra)} (only PRD.md, issues.json and issue-<n>.md)")
    for k in range(1, n + 1):
        files[f"issue-{k}.md"] = _read(dir_, f"issue-{k}.md", 4000 * 4 + 64)      # message_max characters; a character is up to 4 bytes
    return files


def folder_sha(files):
    """sha256 of the canonical JSON [[name, sha256(bytes)], ...] in the fixed order."""
    order = ["PRD.md", "issues.json", *sorted((k for k in files if k.startswith("issue-")), key=lambda k: int(k[6:-3]))]
    return hashlib.sha256(json.dumps([[k, hashlib.sha256(files[k]).hexdigest()] for k in order], separators=(",", ":")).encode()).hexdigest()


def _proxy_problem(path):
    """Why the viewer's proxy does not forward this full path (query included), or None."""
    if not PLAIN.fullmatch(path):
        return "has a space or a control character"
    m = sv.API.match(path)
    if not m or m.end() != len(path):
        return "is not forwarded by the proxy (router/stage_viewer.py:76)"
    return None


def _field_problem(ref):
    parts = ref.split(".") if isinstance(ref, str) else []
    if len(parts) == 2 and parts[0] in TABLES:
        return None if parts[1] in TABLES[parts[0]] or parts[1] in PUBLISHED_EXTRA.get(parts[0], ()) else "is not published by the snapshot"
    if len(parts) == 3 and parts[0] == "EVENT_FIELDS" and parts[1] in sd.EVENT_FIELDS:
        return None if parts[2] in sd.EVENT_FIELDS[parts[1]] else "is not published by the snapshot"
    return "is not <TABLE>.<name> of JOB_FIELDS, STAGE_FIELDS, LOG_FIELDS or EVENT_FIELDS.<event>.<name>"


def _hits(text):
    """[(path, template)] for every /api/... and `GET /path` in an issue's text: left boundary, trailing punctuation cut; a hit that the text continues with
    < { $ or :name is a prefix of a templated path (/api/jobs/<id>/draft, ${id}, :id), not a path of its own."""
    spans = [(m.start(), m.end()) for m in API_HIT.finditer(text)] + [(m.start(1), m.end(1)) for m in VERB_HIT.finditer(text)]
    out = []
    for start, end in spans:
        path = text[start:end].rstrip(TAIL)
        if path in ("", "/", "/api/"):                  # a bare slash or "the /api/ routes": a prefix mentioned, not a path
            continue
        template = path.endswith("/") and (text[end:end + 1] in ("<", "{", "$") or re.match(r":[A-Za-z]", text[end:end + 2]) is not None)
        out.append((path, template))
    return out


def check(files, *, cfg, queues_dir=rq.QUEUES, jobs_dir=rj.JOBS):
    """([(level, text)], parsed) of the folder's bytes: the findings and what `approve` needs (None if issues.json is unusable)."""
    f = []

    def add(level, text):
        f.append((level, text))
    try:
        spec = json.loads(files["issues.json"].decode("utf-8"))
        texts = [files[f"issue-{k}.md"].decode("utf-8") for k in range(1, len(spec["items"]) + 1)]
        files["PRD.md"].decode("utf-8")
    except (UnicodeDecodeError, ValueError, KeyError, TypeError, RecursionError) as e:
        add(BLOCK, f"the folder is not valid UTF-8 JSON and issue files ({type(e).__name__})")
        return f, None
    if not isinstance(spec, dict) or set(spec) != TOP_KEYS or not isinstance(spec["items"], list):
        add(BLOCK, f"issues.json must be an object with exactly the keys {sorted(TOP_KEYS)}")
        return f, None
    if type(spec["max_usd"]) not in (int, float) or not isinstance(spec["commit"], str) or not re.fullmatch(r"[0-9a-f]{40}", spec["commit"]) or not isinstance(spec["repo"], str):
        add(BLOCK, "issues.json: repo is a name, commit 40 hex, max_usd a number (not a string or a boolean)")
        return f, None
    try:
        v = rq.validate_new(repo=spec["repo"], commit=spec["commit"], max_usd=spec["max_usd"], issues=texts, cfg=cfg, queues_dir=queues_dir, jobs_dir=jobs_dir)
    except (rj.Refused, ValueError, TypeError) as e:
        add(BLOCK, str(e))
        v = None
    declared_all = set()
    for i, item in enumerate(spec["items"], 1):
        where = f"item {i}"
        if not isinstance(item, dict) or not set(item) <= ITEM_KEYS or type(item.get("n")) is not int or item.get("n") != i or not isinstance(item.get("paths", []), list) or not isinstance(item.get("fields", []), list):
            add(BLOCK, f"{where}: must be an object with n = {i} and only the keys {sorted(ITEM_KEYS)}")
            continue
        declared = set()
        for p in item.get("paths", []):
            if not isinstance(p, dict) or not set(p) <= PATH_KEYS or p.get("side") not in SIDES or not isinstance(p.get("path"), str):
                add(BLOCK, f"{where}: a path needs side ({' or '.join(SIDES)}) and path, and only the keys {sorted(PATH_KEYS)}")
                continue
            path, side = p["path"], p["side"]
            if not PLAIN.fullmatch(path):
                add(BLOCK, f"{where}: path {ascii(path)} has a space or a control character")
                continue
            if side == "viewer-api":
                if "via_proxy" in p:
                    add(BLOCK, f"{where}: via_proxy belongs to side ledger")
                full = path
            else:
                if not isinstance(p.get("via_proxy"), bool):
                    add(BLOCK, f"{where}: ledger path {path}: via_proxy must be true or false (will the viewer call it through the proxy?)")
                    continue
                if not path.startswith("/") or path == "/api" or path.startswith("/api/") or path.startswith("/api?"):
                    add(BLOCK, f"{where}: ledger path {path} must start with / and not with /api (that is the viewer's side)")
                    continue
                full = "/api" + path if p["via_proxy"] else None
            declared.add(path)
            if full is not None:
                why = _proxy_problem(full)
                if why:
                    add(BLOCK, f"{where}: {full} {why}: a strict-lane Argus change and a proxy restart first, outside the queue")
        for ref in item.get("fields", []):
            why = _field_problem(ref)
            if why:
                add(BLOCK, f"{where}: field {ref} {why}: a strict-lane Argus change first" if "published" in why else f"{where}: field {ref} {why}")
        text = texts[i - 1] if i - 1 < len(texts) else ""
        for path, template in _hits(text):
            if template:
                if not any(d.startswith(path) for d in declared):
                    add(WARN, f"{where}: the text names a templated path starting {path}; declare the full path")
            elif path not in declared:
                add(BLOCK, f"{where}: the text names {path} but it is not in this item's paths: declare it (a ledger path with via_proxy true or false)")
        declared_all |= declared
    if not files["PRD.md"].strip():
        add(WARN, "PRD.md is empty")
    elif b"kontrak" not in files["PRD.md"].lower() and b"contract" not in files["PRD.md"].lower():
        add(WARN, "PRD.md does not mention the contract")
    return f, {"spec": spec, "texts": texts, "valid": v}


def report(dir_, *, cfg, queues_dir=rq.QUEUES, jobs_dir=rj.JOBS):
    """(text, ok): what `argus prd check` prints."""
    try:
        files = read_folder(dir_)
    except Folder as e:
        return f"BLOCK {e}", False
    f, _ = check(files, cfg=cfg, queues_dir=queues_dir, jobs_dir=jobs_dir)
    blocked = any(level == BLOCK for level, _ in f)
    lines = [f"{level:5} {text}" for level, text in f]
    lines.append(f"prd sha {folder_sha(files)}")
    lines.append("checked: the declared paths and fields, and every /api/... and `GET|HEAD|POST|PUT|PATCH|DELETE /path` (upper case) in the issue texts; a path built from pieces, written /API/, %2F or `get /x` is not seen. "
                 "Nothing here judges whether the PRD is good.")
    lines.append("BLOCKED: nothing can be approved" if blocked else f"no BLOCK: argus prd approve {dir_} --sha {folder_sha(files)[:12]}")
    return "\n".join(lines), not blocked


def approve(dir_, sha, *, cfg, deps, queues_dir=rq.QUEUES, jobs_dir=rj.JOBS):
    """The human approves the folder they saw: the same check on the same bytes, then a PENDING queue with `prd` recorded. Returns the queue."""
    try:
        files = read_folder(dir_)
    except Folder as e:
        raise rj.Refused(f"{e}; nothing was approved") from None
    full = folder_sha(files)
    sha = sha.strip().lower() if isinstance(sha, str) else sha
    if not isinstance(sha, str) or not rj.SHA_SEEN.fullmatch(sha) or not full.startswith(sha):
        raise rj.Refused(f"the folder is {full[:12]}, not the {sha!r} given (check shows it); nothing was approved")
    f, parsed = check(files, cfg=cfg, queues_dir=queues_dir, jobs_dir=jobs_dir)
    blocks = [t for level, t in f if level == BLOCK]
    if blocks or parsed is None:
        raise rj.Refused("BLOCK: " + "; ".join(blocks) + "; nothing was approved")
    s = parsed["spec"]
    return rq.new(repo=s["repo"], commit=s["commit"], max_usd=s["max_usd"], issues=parsed["texts"], cfg=cfg, deps=deps, queues_dir=queues_dir, jobs_dir=jobs_dir,
                  prd={"sha": full, "dir": str(Path(dir_).resolve())})
