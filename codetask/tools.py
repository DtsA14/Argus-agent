"""The agent's tools for a code task. Every path goes through the path jail of the workspace; writes are checked
against the frozen contract's scope before anything is written (acceptance re-checks the result anyway).

Results are written so a tool run twice on the same workspace gives the same text (no timings, no "created"
versus "overwritten"): after a crash between running a tool and committing its result, the tool runs again and the
conversation continues exactly as it would have.
"""
import hashlib
import json
import re
from typing import List

from pydantic import BaseModel, Field

from acceptance.claims import schema_problems
from acceptance.contract import SUMMARY, matches
from acceptance.validation import run_validation
from acceptance.workspace import snapshot
from tools.fs import PathEscape, PathJail

MAX_READ = 100_000
MAX_WRITE = 200_000


class ListFiles(BaseModel):
    """List every file in the workspace (paths relative to the repository root)."""


class ReadFile(BaseModel):
    """Read one text file of the workspace."""
    path: str = Field(description="Path relative to the repository root, e.g. src/calc.py")


class WriteFile(BaseModel):
    """Replace the whole content of one file (or create it). Only files in the writable scope may be written."""
    path: str = Field(description="Path relative to the repository root")
    content: str = Field(description="The complete new file content")


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


TOOLS = [ListFiles, ReadFile, WriteFile, RunValidation, Finish]
GATED = {"ListFiles": "list_files", "ReadFile": "read_file", "WriteFile": "write_file",
         "RunValidation": "run_validation"}     # Finish ends the attempt; it is not a gated tool
TIMING = re.compile(r"in \d+(\.\d+)?s\b")


def offered(allowed):
    return [t for t in TOOLS if t is Finish or GATED[t.__name__] in allowed]


def claims_doc(args):
    """Finish arguments -> the claims_v1 document, keeping only the field each claim kind uses."""
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

    def __init__(self, workspace, contract, sandbox_cfg, allowed, log, validate=run_validation):
        self.jail = PathJail(workspace)
        self.workspace, self.contract, self.sandbox_cfg = workspace, contract, sandbox_cfg
        self.allowed, self.log, self.validate = set(allowed), log, validate

    def _gate(self, name):
        tool = GATED[name]
        if tool not in self.allowed:
            self.log.emit("tool_denied", role="coder", tool=tool)
            return f"Denied: {name} is not allowed for this role."
        self.log.emit("tool_call", role="coder", tool=tool)
        return None

    def run(self, call):
        """Execute one tool call -> {"content": text for the model, "finished": bool}."""
        name, args = call.get("name"), call.get("args") or {}
        if name == "Finish":
            return self.finish(args)
        if name not in GATED:
            return {"content": f"Unknown tool {name!r}.", "finished": False}
        denied = self._gate(name)
        if denied:
            return {"content": denied, "finished": False}
        try:
            return {"content": getattr(self, name.lower())(args), "finished": False}
        except PathEscape as e:
            return {"content": f"Refused: {e}", "finished": False}
        except FileNotFoundError:
            return {"content": f"No such file: {args.get('path')!r}", "finished": False}

    def listfiles(self, args):
        return "\n".join(sorted(snapshot(self.workspace)))

    def readfile(self, args):
        return self.jail.read_text(str(args.get("path", "")), max_bytes=MAX_READ)

    def writefile(self, args):
        path, content = args.get("path"), args.get("content")
        if not isinstance(path, str) or not isinstance(content, str):
            return "Rejected: WriteFile needs a string 'path' and a string 'content'."
        self.jail.parts(path)                                    # PathEscape before any scope decision
        norm = "/".join(self.jail.parts(path))
        sc = self.contract["scope"]
        if norm == SUMMARY:
            return f"Rejected: {SUMMARY} is written by Finish, not WriteFile."
        if matches(norm, sc["protected"]):
            return f"Rejected: {norm} is protected by the contract and may not be changed."
        if not matches(norm, sc["writable"]):
            return f"Rejected: {norm} is outside the writable scope {sc['writable']}."
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
        v = self.validate(spec, self.workspace, self.sandbox_cfg, self.log)
        ev = v.get("evidence") or {}
        out = {"status": v["status"], "reason": v["reason"],
               **{k: ev.get(k) for k in ("tests_run", "failures", "errors", "skipped", "must_pass") if k in ev},
               "output_tail": TIMING.sub("in Xs", (ev.get("output_tail") or "")[-1500:])}
        return json.dumps(out, ensure_ascii=False, sort_keys=True)

    def finish(self, args):
        doc = claims_doc(args)
        problems = schema_problems(doc)
        if problems:
            return {"content": "Rejected, nothing was written:\n- " + "\n- ".join(problems), "finished": False}
        self.jail.write_text(SUMMARY, json.dumps(doc, ensure_ascii=False, sort_keys=True, indent=2))
        return {"content": f"{SUMMARY} written; the attempt is over and the harness now checks the contract.",
                "finished": True}
