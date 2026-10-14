from pathlib import Path

from dataset import load_rows
from harness.errors import PermissionDenied


def read_data():
    return load_rows()


def write_file(path, text):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return str(p)


def run_shell(cmd):
    raise NotImplementedError("sandboxed shell arrives in milestone 2")


TOOLS = {"read_data": read_data, "write_file": write_file, "run_shell": run_shell}


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
