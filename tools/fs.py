"""File access confined to an allowed root (path jail).

Rules, applied to every file tool:
  - paths are relative to the root; absolute paths, NUL bytes, empty paths and the root itself are
    refused; `..` is resolved lexically and may never climb above the root;
  - no symlink is followed anywhere below the root. Every directory component is opened with
    openat(dir_fd, name, O_DIRECTORY | O_NOFOLLOW) relative to the descriptor of its already-opened
    parent, and the file itself with O_NOFOLLOW relative to the descriptor of its directory. A symlink
    at any level is refused, even one pointing inside the root;
  - only regular files are read (a FIFO or device is refused without blocking);
  - writes are atomic and safe to repeat: a temp file in the same directory (via its descriptor),
    fsync, then renameat into place, then fsync of the directory. Running the same write twice
    (e.g. after a crash) leaves the same file.

Threat model. Paths come from the model (untrusted); the jail must hold against any path string. It
must also hold against a concurrent local process that can modify directories *inside* the root
(e.g. sandboxed code writing into its workspace while the harness writes a file there): because each
step is relative to a descriptor that was opened without following links, swapping a parent directory
for a symlink after it was checked cannot redirect the operation outside; the operation either is
refused or lands in the directory that was opened. Out of scope: an attacker who can change the root
path itself or anything above it (the root is trusted configuration, opened once per operation), and
hard links to outside files created by such an attacker (they need write access outside the root).
"""
import os
import stat
import uuid
from pathlib import Path

_DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)


class PathEscape(Exception):
    """The path is outside the allowed root, or otherwise not acceptable."""


class PathJail:
    def __init__(self, root):
        # os.replace is not listed in supports_dir_fd but shares renameat with os.rename
        if not {os.open, os.rename, os.mkdir, os.unlink, os.stat} <= os.supports_dir_fd:
            raise RuntimeError("PathJail needs openat/renameat (dir_fd) support")
        self.root = Path(root).resolve()

    # -- path validation (lexical, no file system access) ---------------------------------------
    def parts(self, rel):
        if not isinstance(rel, str) or not rel.strip():
            raise PathEscape("empty path")
        if "\x00" in rel:
            raise PathEscape("NUL byte in path")
        if os.path.isabs(rel):
            raise PathEscape(f"absolute path not allowed: {rel!r}")
        out = []
        for p in rel.split("/"):
            if p in ("", "."):
                continue
            if p == "..":
                if not out:
                    raise PathEscape(f"path escapes the allowed root: {rel!r}")
                out.pop()
                continue
            out.append(p)
        if not out:
            raise PathEscape("path is the root itself, not a file")
        return out

    def resolve(self, rel):
        """The path the operation would use, inside the root. Validation only: operations never
        re-open this path string, they walk from the root by descriptor."""
        return self.root.joinpath(*self.parts(rel))

    # -- descriptor walk ----------------------------------------------------------------------------
    def _race(self, stage, rel):
        """Test hook: called at fixed points of an operation so tests can swap directories mid-way."""

    def _open_dir(self, dirs, rel, create):
        fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_CLOEXEC", 0))
        try:
            for name in dirs:
                if create:
                    try:
                        os.mkdir(name, 0o755, dir_fd=fd)
                    except FileExistsError:
                        pass
                try:
                    nfd = os.open(name, _DIR_FLAGS, dir_fd=fd)
                except FileNotFoundError:
                    raise
                except OSError as e:           # ELOOP (symlink) or ENOTDIR (a file)
                    raise PathEscape(f"not a plain directory (symlink or file) in path: {rel!r}") from e
                os.close(fd)
                fd = nfd
            return fd
        except BaseException:
            os.close(fd)
            raise

    def _refuse_symlink(self, name, dfd, rel):
        try:
            st = os.stat(name, dir_fd=dfd, follow_symlinks=False)
        except FileNotFoundError:
            return
        if stat.S_ISLNK(st.st_mode):
            raise PathEscape(f"refusing to replace a symlink: {rel!r}")

    # -- operations ---------------------------------------------------------------------------------
    def write_text(self, rel, text):
        parts = self.parts(rel)
        self._race("before_walk", rel)
        dfd = self._open_dir(parts[:-1], rel, create=True)
        name = parts[-1]
        tmp = f".{name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp"
        try:
            self._race("after_walk", rel)
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644, dir_fd=dfd)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(text)
                    f.flush()
                    os.fsync(f.fileno())
                self._refuse_symlink(name, dfd, rel)
                self._race("before_replace", rel)
                os.replace(tmp, name, src_dir_fd=dfd, dst_dir_fd=dfd)
                os.fsync(dfd)
            finally:
                try:
                    os.unlink(tmp, dir_fd=dfd)
                except FileNotFoundError:
                    pass
        finally:
            os.close(dfd)
        return str(self.root.joinpath(*parts))

    def read_text(self, rel, max_bytes=1_000_000):
        parts = self.parts(rel)
        self._race("before_walk", rel)
        dfd = self._open_dir(parts[:-1], rel, create=False)
        try:
            self._race("after_walk", rel)
            try:
                fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dfd)
            except FileNotFoundError:
                raise
            except OSError as e:
                raise PathEscape(f"cannot open as a plain file (symlink?): {rel!r}") from e
        finally:
            os.close(dfd)
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            os.close(fd)
            raise PathEscape(f"not a regular file: {rel!r}")
        with os.fdopen(fd, "rb") as f:
            data = f.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise PathEscape(f"file larger than {max_bytes} bytes: {rel!r}")
        return data.decode("utf-8", errors="replace")
