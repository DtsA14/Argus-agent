"""The agent's tools for a code task. Every path goes through the path jail of the workspace; writes are checked
against the frozen contract's scope before anything is written (acceptance re-checks the result anyway).

After a crash between running a tool and committing its result, the tool runs again. What must be the same is its
effect: a write replaces the whole file atomically, so running it twice leaves the same file (a repeated append would
not). The result text of that uncommitted run was never seen by a committed step, so it need not match; it is still
kept free of timings and of "created" versus "overwritten" so replays read the same.
"""
import hashlib
import json
import os
import re
import stat
from typing import List

from pydantic import BaseModel, Field

from acceptance.claims import schema_problems
from acceptance.contract import SUMMARY, claims_schema, matches
from acceptance.validation import run_validation
from acceptance.workspace import digest, snapshot
from harness.events import TaggedLog
from acceptance.workspace import snapshot
from tools.fs import PathEscape, PathJail

MAX_READ = 100_000
MAX_WRITE = 200_000

# SearchFiles (docs/reviews/DESIGN_SEARCHFILES.md): bounds on the input, the work done and the output of one call.
SEARCH_MAX_TEXT = 200          # characters of the literal text
SEARCH_MAX_MATCHES = 20        # result lines returned
SEARCH_MAX_LINE = 200          # characters kept of each matching line
SEARCH_MAX_FILES = 500         # files read per call
SEARCH_MAX_BYTES = 2_000_000   # bytes read per call
SEARCH_MAX_FILE = 256_000      # a larger file is not read (and is reported)


class ListFiles(BaseModel):
    """List every file in the workspace (paths relative to the repository root)."""


class ReadFile(BaseModel):
    """Read one text file of the workspace."""
    path: str = Field(description="Path relative to the repository root, e.g. src/calc.py")


class SearchFiles(BaseModel):
    """Find a literal piece of text in the repository's files. Read-only. Returns matching lines as
    "path:line: text" in path and line order, at most 20, and says so when the results are incomplete."""
    text: str = Field(description="Literal text to find (not a pattern), case-sensitive, one line")
    path: str = Field(default="", description="Optional: only search under this directory, e.g. src")


class WriteFile(BaseModel):
    """Replace the whole content of one file (or create it). Only files in the writable scope may be written."""
    path: str = Field(description="Path relative to the repository root")
    content: str = Field(description="The complete new file content")


class EditFile(BaseModel):
    """Replace one exact piece of text in one file with new text. The old text must occur exactly once in the file;
    otherwise nothing changes. Only files in the writable scope may be edited. For changing part of a file."""
    path: str = Field(description="Path relative to the repository root")
    old_text: str = Field(description="The exact text to replace, including whitespace; it must occur exactly once")
    new_text: str = Field(description="The text that replaces it")


class RunValidation(BaseModel):
    """Run one of the contract's validation commands in the sandbox and see its result. Changes nothing."""
    id: str = Field(description="The validation id from the contract")


class Claim(BaseModel):
    claim: str = Field(description="tests_pass, issue_fixed or file_changed")
    evidence: str = Field(default="", description="For tests_pass / issue_fixed: validation:<id>")
    path: str = Field(default="", description="For file_changed: the path you changed")


class Finish(BaseModel):
    """End this attempt. The harness writes SUMMARY.json from these claims and then checks everything itself."""
    claims: List[Claim] = Field(description="What you claim, each backed by evidence the harness can check")
    summary: str = Field(description="One or two sentences on what you changed")


TOOLS = [ListFiles, SearchFiles, ReadFile, WriteFile, EditFile, RunValidation, Finish]
GATED = {"ListFiles": "list_files", "SearchFiles": "search_files", "ReadFile": "read_file",
         "WriteFile": "write_file", "EditFile": "edit_file",
         "RunValidation": "run_validation"}   # Finish ends the attempt; it is not gated
TIMING = re.compile(r"in \d+(\.\d+)?s\b")


def offered(allowed):
    return [t for t in TOOLS if t is Finish or GATED[t.__name__] in allowed]


def claims_doc(args):
    """Finish arguments -> the claims document, keeping only the field each claim kind uses."""
    out = []
    for c in args.get("claims") or []:
        if not isinstance(c, dict):
            out.append(c)
            continue
        field = {"file_changed": "path"}.get(c.get("claim"), "evidence")
        out.append({"claim": c.get("claim"), field: c.get(field, "")})
    return {"claims": out, "summary": args.get("summary")}


class Toolbox:
    """allowed: the coder role's tool allowlist from config (tools.coder), enforced here, not by the prompt."""

    def __init__(self, workspace, contract, sandbox_cfg, allowed, log, validate=run_validation, journal=None,
                 crasher=None, role="coder"):
        """journal: a file outside the workspace where EditFile records each edit before making it (crash-resume).
        role: the role named in tool_call / tool_denied events (the W2b drafter uses the read tools)."""
        self.jail = PathJail(workspace)
        self.workspace, self.contract, self.sandbox_cfg = workspace, contract, sandbox_cfg
        self.allowed, self.log, self.validate = set(allowed), log, validate
        self.journal, self.crasher, self.role = journal, crasher, role

    def _gate(self, name):
        tool = GATED[name]
        if tool not in self.allowed:
            self.log.emit("tool_denied", role=self.role, tool=tool)
            return f"Denied: {name} is not allowed for this role."
        self.log.emit("tool_call", role=self.role, tool=tool)
        return None

    def run(self, call, step_key=None):
        """Execute one tool call -> {"content": text for the model, "finished": bool}. step_key: the memo key of this
        tool step, the same when a crashed step runs again; EditFile needs it to be safe to repeat."""
        name, args = call.get("name"), call.get("args") or {}
        if name == "Finish":
            return self.finish(args)
        if name not in GATED:
            return {"content": f"Unknown tool {name!r}.", "finished": False}
        denied = self._gate(name)
        if denied:
            return {"content": denied, "finished": False}
        try:
            if name == "EditFile":
                return {"content": self.editfile(args, step_key), "finished": False}
            return {"content": getattr(self, name.lower())(args), "finished": False}
        except PathEscape as e:
            return {"content": f"Refused: {e}", "finished": False}
        except FileNotFoundError:
            return {"content": f"No such file: {args.get('path')!r}", "finished": False}

    def listfiles(self, args):
        return "\n".join(sorted(snapshot(self.workspace)))

    def searchfiles(self, args):
        """Literal, case-sensitive search over regular files under the workspace (or under `path`, or in the one
        regular file `path` names: SPEC_LOCATE_FROM_TRACEBACK 2.3). Every read goes through the path jail; symlinks
        and special files are never followed or read. Bounded in files and bytes read, in files too large to read, and
        in result lines; any bound reached is reported as incomplete."""
        text, under = args.get("text"), args.get("path") or ""
        if not isinstance(text, str) or not 1 <= len(text) <= SEARCH_MAX_TEXT or "\n" in text or "\r" in text:
            return f"Rejected: text must be one line of 1 to {SEARCH_MAX_TEXT} characters."
        if not isinstance(under, str):
            return "Rejected: path must be a directory or file path."
        prefix, single = (), False
        if under not in ("", ".", "./"):                                # "/" and other absolute paths: refused
            prefix = tuple(self.jail.parts(under))                     # PathEscape: '..', absolute, NUL
            cur = self.jail.root
            for n, part in enumerate(prefix, 1):                       # a real directory, or the last a regular file
                cur = cur / part
                try:
                    st = os.lstat(cur)
                except FileNotFoundError:
                    return f"No such directory: {under!r}"
                if stat.S_ISLNK(st.st_mode):
                    raise PathEscape(f"refusing to search through a symlink: {under!r}")
                if stat.S_ISREG(st.st_mode) and n == len(prefix):
                    single = True                                      # the last component: search this file only
                elif not stat.S_ISDIR(st.st_mode):
                    return f"Rejected: {under!r} is not a directory or a regular file."
        start = self.jail.root.joinpath(*prefix)
        hits, large, files, read, stopped = [], [], 0, 0, False
        walk = [(str(start.parent), [], [start.name])] if single else os.walk(start, followlinks=False)
        for dirpath, dirnames, filenames in walk:
            here = os.path.relpath(dirpath, self.jail.root)
            dirnames[:] = sorted(d for d in dirnames if not os.path.islink(os.path.join(dirpath, d)))
            for name in sorted(filenames):
                rel = name if here == "." else f"{here}/{name}".replace(os.sep, "/")
                st = os.lstat(os.path.join(dirpath, name))
                if not stat.S_ISREG(st.st_mode):
                    continue                                           # symlink, FIFO, device: never read
                if st.st_size > SEARCH_MAX_FILE:
                    large.append(rel)
                    continue
                if files >= SEARCH_MAX_FILES or read + st.st_size > SEARCH_MAX_BYTES:
                    stopped = True
                    break
                files += 1
                read += st.st_size
                for n, line in enumerate(self.jail.read_text(rel, max_bytes=SEARCH_MAX_FILE).splitlines(), 1):
                    if text in line:
                        hits.append(f"{rel}:{n}: {line.strip()[:SEARCH_MAX_LINE]}")
            if stopped:
                break
        out = hits[:SEARCH_MAX_MATCHES] or [f"No matches in the {files} files searched." if stopped else "No matches."]
        if len(hits) > SEARCH_MAX_MATCHES:
            out.append(f"... {len(hits) - SEARCH_MAX_MATCHES} more matches not shown: results incomplete, "
                       "narrow the text or the path.")
        if stopped:
            out.append(f"... search stopped after {files} files ({read} bytes), the limit for one search: results "
                       "incomplete, narrow the path.")
        if large:
            out.append(f"... {len(large)} file(s) larger than {SEARCH_MAX_FILE} bytes were not searched: "
                       + ", ".join(large[:5]) + (" ..." if len(large) > 5 else ""))
        return "\n".join(out)

    def readfile(self, args):
        return self.jail.read_text(str(args.get("path", "")), max_bytes=MAX_READ)

    def _writable(self, path, tool):
        """(normalised path, None) when path may be written, else (None, the reason). The same rules for every write."""
        norm = "/".join(self.jail.parts(path))                  # PathEscape before any scope decision
        sc = self.contract["scope"]
        if norm == SUMMARY:
            return None, f"Rejected: {SUMMARY} is written by Finish, not {tool}."
        if matches(norm, sc["protected"]):
            return None, f"Rejected: {norm} is protected by the contract and may not be changed."
        if not matches(norm, sc["writable"]):
            return None, f"Rejected: {norm} is outside the writable scope {sc['writable']}."
        return norm, None

    def writefile(self, args):
        path, content = args.get("path"), args.get("content")
        if not isinstance(path, str) or not isinstance(content, str):
            return "Rejected: WriteFile needs a string 'path' and a string 'content'."
        norm, problem = self._writable(path, "WriteFile")
        if problem:
            return problem
        if len(content.encode("utf-8")) > MAX_WRITE:
            return f"Rejected: content larger than {MAX_WRITE} bytes."
        self.jail.write_text(norm, content)
        h = hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]
        return f"{norm} now has {len(content.encode('utf-8'))} bytes (sha256 {h})."

    def runvalidation(self, args):
        specs = {v["id"]: v for v in self.contract["validation"]}
        spec = specs.get(args.get("id"))
        if spec is None:
            return f"Unknown validation {args.get('id')!r}. Available: {sorted(specs)}."
        v = self.validate(spec, self.workspace, self.sandbox_cfg, TaggedLog(self.log, origin="tool"))
        ev = v.get("evidence") or {}
        out = {"status": v["status"], "reason": v["reason"],
               **{k: ev.get(k) for k in ("tests_run", "failures", "errors", "skipped", "must_pass") if k in ev},
               "output_tail": TIMING.sub("in Xs", (ev.get("output_tail") or "")[-1500:])}
        return json.dumps(out, ensure_ascii=False, sort_keys=True)

    def digest(self):
        """The workspace's digest, computed as the verdict computes it."""
        return digest(snapshot(self.workspace))

    def validate_all(self):
        """D3: every validation of the contract, in contract order, as RunValidation runs one (read-only sandbox)."""
        log = TaggedLog(self.log, origin="auto")
        return [self.validate(spec, self.workspace, self.sandbox_cfg, log) for spec in self.contract["validation"]]

    def finish(self, args):
        doc = claims_doc(args)
        problems = schema_problems(doc, claims_schema(self.contract))
        if problems:
            return {"content": "Rejected, nothing was written:\n- " + "\n- ".join(problems), "finished": False}
        self.jail.write_text(SUMMARY, json.dumps(doc, ensure_ascii=False, sort_keys=True, indent=2))
        return {"content": f"{SUMMARY} written; the attempt is over and the harness now checks the contract.",
                "finished": True}

    # ---- EditFile: one exact, unique replacement, safe to run again after a crash ------------------------------
    #
    # An edit is not idempotent by itself: when new_text contains old_text (an insertion), applying it twice inserts
    # twice. So before writing, the edit is recorded in a journal outside the workspace under this tool step's memo
    # key, with the file's hash before and after. Writing the file is atomic (temp file, fsync, rename), so after a
    # crash the file holds either the before or the after content:
    #   entry, file == after     the edit was made and its result not committed: report it again, change nothing
    #   entry, file == before    the crash fell between journal and write: make the same edit (same input, result)
    #   entry, file elsewise     refuse and change nothing (cannot happen without interference from outside)
    #   no entry                 a first run: check, record, then write
    # Another step (another key) is a new edit, even with the same arguments.

    def _journaled(self, key):
        found = None
        try:
            with open(self.journal, encoding="utf-8") as f:
                for line in f:
                    try:
                        e = json.loads(line)
                    except ValueError:
                        continue                                 # cut off by a crash before its write: ignored
                    if e.get("key") == key:
                        found = e
        except FileNotFoundError:
            pass
        return found

    def _record(self, key, norm, before, after):
        with open(self.journal, "a", encoding="utf-8") as f:
            f.write(json.dumps({"key": key, "path": norm, "before": before, "after": after}) + "\n")
            f.flush()
            os.fsync(f.fileno())

    @staticmethod
    def _edited(norm, text):
        data = text.encode("utf-8")
        return f"{norm} edited: 1 occurrence replaced; it now has {len(data)} bytes (sha256 {_sha(data)[:12]})."

    def editfile(self, args, step_key):
        path, old, new = args.get("path"), args.get("old_text"), args.get("new_text")
        if not (isinstance(path, str) and isinstance(old, str) and isinstance(new, str)):
            return "Rejected: EditFile needs a string 'path', 'old_text' and 'new_text'."
        if not old:
            return "Rejected: old_text must not be empty."
        if old == new:
            return "Rejected: old_text and new_text are the same; nothing to change."
        if self.journal is None or step_key is None:
            return "Refused: EditFile is not available here (no step journal)."
        norm, problem = self._writable(path, "EditFile")
        if problem:
            return problem
        current = self.jail.read_text(norm, max_bytes=MAX_READ)  # FileNotFoundError, PathEscape: reported by run()
        if "\ufffd" in current:
            return f"Rejected: {norm} is not plain UTF-8 text; nothing changed."
        key = _sha(step_key.encode("utf-8"))
        cur = _sha(current.encode("utf-8"))
        entry = self._journaled(key)
        if entry is not None:
            if entry.get("path") != norm:
                return "Refused: this step's edit was recorded for another file; nothing changed."
            if cur == entry["after"]:
                return self._edited(norm, current)
            if cur != entry["before"]:
                return f"Refused: {norm} changed after this edit was recorded; nothing changed."
        n = current.count(old)
        if n == 0:
            return f"Rejected: old_text was not found in {norm}; nothing changed."
        if n > 1:
            return (f"Rejected: old_text occurs {n} times in {norm}; include more surrounding text so that it occurs "
                    f"exactly once. Nothing changed.")
        result = current.replace(old, new, 1)
        if len(result.encode("utf-8")) > MAX_WRITE:
            return f"Rejected: the edited file would be larger than {MAX_WRITE} bytes; nothing changed."
        after = _sha(result.encode("utf-8"))
        if entry is None:
            self._record(key, norm, cur, after)
        elif entry["after"] != after:
            return "Refused: this step's edit was recorded with a different result; nothing changed."
        if self.crasher is not None:
            self.crasher.point("edit@after_journal")
        self.jail.write_text(norm, result)
        return self._edited(norm, result)


def _sha(data):
    return hashlib.sha256(data).hexdigest()
