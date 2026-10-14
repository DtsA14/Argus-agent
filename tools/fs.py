"""File access confined to an allowed root (path jail).

Rules, applied to every file tool:
  - paths are relative to the root; absolute paths, NUL bytes and empty paths are refused;
  - the path is resolved (following symlinks) and must stay inside the resolved root, so `..` and
    symlinks pointing outside are refused, whether the link is the file itself or a parent directory;
  - the final component is opened with O_NOFOLLOW, so a symlink swapped in after the check is refused;
  - writes are atomic and safe to repeat: a temp file in the same directory, fsync, then os.replace.
    Running the same write twice (e.g. after a crash) leaves the same file.
"""
import os
from pathlib import Path


class PathEscape(Exception):
    """The path is outside the allowed root, or otherwise not acceptable."""


class PathJail:
    def __init__(self, root):
        self.root = Path(root).resolve()

    def resolve(self, rel):
        if not isinstance(rel, str) or not rel.strip():
            raise PathEscape("empty path")
        if "\x00" in rel:
            raise PathEscape("NUL byte in path")
        if os.path.isabs(rel):
            raise PathEscape(f"absolute path not allowed: {rel!r}")
        target = (self.root / rel).resolve()
        if target != self.root and not target.is_relative_to(self.root):
            raise PathEscape(f"path escapes the allowed root: {rel!r}")
        if target == self.root:
            raise PathEscape("path is the root itself, not a file")
        return target

    def write_text(self, rel, text):
        target = self.resolve(rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        # re-check after mkdir: a parent created as/through a symlink must still resolve inside
        if not target.parent.resolve().is_relative_to(self.root):
            raise PathEscape(f"parent directory escapes the allowed root: {rel!r}")
        tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
                f.flush()
                os.fsync(f.fileno())
            if target.is_symlink():
                raise PathEscape(f"refusing to replace a symlink: {rel!r}")
            os.replace(tmp, target)
        finally:
            if tmp.exists():
                tmp.unlink()
        return str(target)

    def read_text(self, rel, max_bytes=1_000_000):
        target = self.resolve(rel)
        fd = os.open(target, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as f:
            data = f.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise PathEscape(f"file larger than {max_bytes} bytes: {rel!r}")
        return data.decode("utf-8", errors="replace")
