from dataset import load_rows
from harness.errors import PermissionDenied

from .fs import PathJail


def read_data():
    return load_rows()


def write_file(root, rel, text):
    """Write `text` to `rel` inside `root` only (path jail, atomic, safe to repeat)."""
    return PathJail(root).write_text(rel, text)


def run_python(code, *, workdir, data_dir, sandbox_cfg, log=None, meta=None):
    """Run Python in the Docker sandbox. There is no unsandboxed fallback."""
    from .sandbox import run_python as _run
    return _run(code, workdir=workdir, data_dir=data_dir, cfg=sandbox_cfg, log=log, meta=meta)


TOOLS = {"read_data": read_data, "write_file": write_file, "run_python": run_python}


class ToolGate:
    """Every tool call goes through here; the allowlist comes from config, not from prompts."""

    def __init__(self, role, allowed, log):
        self.role = role
        self.allowed = set(allowed)
        self.log = log

    def call(self, name, *args, **kwargs):
        if name not in self.allowed:
            self.log.emit("tool_denied", role=self.role, tool=name)
            raise PermissionDenied(f"{self.role} may not use {name}")
        self.log.emit("tool_call", role=self.role, tool=name)
        return TOOLS[name](*args, **kwargs)
