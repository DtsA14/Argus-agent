"""Run model-written Python in a locked-down Docker container. There is no unsandboxed fallback:
if Docker or the pinned image is not available, run_python raises SandboxUnavailable.

Every flag below was checked for real effect inside a container (see tests/test_sandbox.py):
  --network none                      no network at all
  --read-only + --tmpfs /tmp          root filesystem read-only; small writable /tmp in memory
  --user 65534:65534                  runs as nobody
  --cap-drop ALL                      no Linux capabilities (CapEff 0)
  --security-opt no-new-privileges    setuid binaries cannot raise privileges (NoNewPrivs 1)
  --memory / --memory-swap            hard memory limit, no swap (exceeding it kills the process: exit 137)
  --cpus, --pids-limit                CPU quota; process count limit (fork bombs are refused)
  -v workdir:/workspace:rw            the only writable host directory (one per worker task)
  -v data_dir:/data:ro                input data, read-only
  --log-driver none                   Docker's default json-file driver copies everything the code prints
                                      to the host disk, unbounded; output reaches the harness only
                                      through the attached pipes, read with a bound (see run_python)
  -i                                  the code is sent on stdin; without -i Docker drops stdin and the
                                      container "succeeds" without running anything
The image must be pinned (name@sha256:... or an image id sha256:...), so a run is reproducible and a
changed image changes the tool version used in memo keys.
"""
import os
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path


class SandboxUnavailable(Exception):
    """Docker, its daemon, or the pinned image is not available. Code is never run outside the sandbox."""


DEFAULTS = {
    "kind": "docker",
    "docker": "docker",
    "image": None,
    "memory": "512m",
    "cpus": "1",
    "pids": 128,
    "tmpfs_size": "64m",
    "timeout_s": 60,
    "max_output_bytes": 65536,          # kept per stream; the rest is drained and discarded, never buffered
    "kill_after_output_bytes": 16 << 20,  # total output after which the container is killed early
    "cleanup_timeout_s": 15,            # total time allowed for kill/remove/join after the run ends
    "allow_unpinned": False,
}


def settings(cfg):
    s = {**DEFAULTS, **(cfg or {})}
    env_image = os.environ.get("ARGUS_SANDBOX_IMAGE")
    if env_image:
        s["image"] = env_image
    return s


def is_pinned(image):
    return bool(image) and ("@sha256:" in image or image.startswith("sha256:"))


def tool_version(cfg):
    """Part of the memo key of RunPython steps: a different image never reuses old results."""
    return f"1:{settings(cfg)['image']}"


def status(cfg):
    """(ok, reason). Checks the binary, the daemon and the pinned image, without running any code."""
    s = settings(cfg)
    if s["kind"] != "docker":
        return False, f"sandbox.kind is {s['kind']!r}, not 'docker'"
    if not s["image"]:
        return False, "no sandbox image configured (sandbox.image or ARGUS_SANDBOX_IMAGE)"
    if not is_pinned(s["image"]) and not s["allow_unpinned"]:
        return False, f"sandbox image {s['image']!r} is not pinned to a digest (name@sha256:... or sha256:...)"
    if shutil.which(s["docker"]) is None:
        return False, f"docker binary {s['docker']!r} not found"
    try:
        r = subprocess.run([s["docker"], "image", "inspect", "--format", "{{.Id}}", s["image"]],
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, f"docker not reachable: {e}"
    if r.returncode != 0:
        return False, f"docker daemon or image not available: {(r.stderr or r.stdout).strip()[:200]}"
    return True, "ok"


def docker_args(s, name, workdir, data_dir, command=None, workspace_mode="rw"):
    """The docker command line. `command` is an argv list run without a shell (default: python reading code
    from stdin); `workspace_mode` "ro" mounts the workspace read-only (validation must not change what it checks).
    data_dir None mounts no data."""
    data = ["-v", f"{data_dir}:/data:ro"] if data_dir is not None else []
    return [
        s["docker"], "run", "--rm", "-i", "--name", name, "--label", "argus.sandbox=1",
        "--network", "none",
        "--read-only", "--tmpfs", f"/tmp:rw,size={s['tmpfs_size']},mode=1777",
        "--user", "65534:65534",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--memory", s["memory"], "--memory-swap", s["memory"],
        "--cpus", str(s["cpus"]), "--pids-limit", str(s["pids"]),
        "-v", f"{workdir}:/workspace:{workspace_mode}", *data,
        "-w", "/workspace",
        "--env", "PYTHONDONTWRITEBYTECODE=1",
        "--log-driver", "none",
        s["image"], *(command or ["python3", "-I", "-"]),
    ]


CHUNK = 65536


class _BoundedReader(threading.Thread):
    """Drains one pipe to EOF, keeping at most `limit` bytes and discarding the rest.

    It never stops reading before EOF: a reader that stopped at the limit would leave the pipe full,
    the program in the container would block on write, and the run would hang until the timeout.
    So the host holds at most `limit` bytes per stream, however much the code prints."""

    def __init__(self, stream, limit, on_total):
        super().__init__(daemon=True)
        self.stream, self.limit, self.on_total = stream, limit, on_total
        self.kept = bytearray()
        self.total = 0

    def run(self):
        fd = self.stream.fileno()
        try:
            while True:
                chunk = os.read(fd, CHUNK)
                if not chunk:
                    break
                self.total += len(chunk)
                room = self.limit - len(self.kept)
                if room > 0:
                    self.kept += chunk[:room]
                self.on_total()
        except OSError:
            pass
        finally:
            self.stream.close()

    @property
    def truncated(self):
        return self.total > len(self.kept)


def _feed(stream, data):
    try:
        stream.write(data)
    except (BrokenPipeError, OSError):
        pass                       # the container exited (or was killed) before reading all the code
    finally:
        try:
            stream.close()
        except OSError:
            pass


def _decode(data, truncated):
    # A cut can split a multi-byte character; drop that partial tail rather than show a broken one.
    text = bytes(data).decode("utf-8", errors="replace")
    if truncated and text.endswith("�"):
        text = bytes(data).decode("utf-8", errors="ignore")
    return text


def _left(deadline):
    return max(0.0, deadline - time.monotonic())


def _docker(s, args, deadline):
    """One docker CLI call bounded by the shared cleanup deadline. None if it failed or ran out of time."""
    if _left(deadline) <= 0:
        return None
    try:
        return subprocess.run([s["docker"], *args], capture_output=True, text=True, timeout=_left(deadline))
    except (OSError, subprocess.TimeoutExpired):
        return None


def _remove(s, name, deadline):
    for cmd in (["kill", name], ["rm", "-f", name]):
        _docker(s, cmd, deadline)


def _container_gone(s, name, deadline):
    """True only when docker positively reports no container with this name (a hung daemon is not 'gone')."""
    r = _docker(s, ["ps", "-a", "-q", "--filter", f"name=^{name}$"], deadline)
    return r is not None and r.returncode == 0 and not r.stdout.strip()


def run_python(code, *, workdir, data_dir, cfg, log=None, meta=None):
    """Run `code` (python, sent on stdin) in the sandbox with the workspace writable. See _run."""
    workdir, data_dir = Path(workdir).resolve(), Path(data_dir).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    os.chmod(workdir, 0o777)   # the container runs as nobody (65534); this directory is its only writable place
    return _run(cfg, lambda s, name: docker_args(s, name, workdir, data_dir), code.encode("utf-8"), log, meta)


def run_command(argv, *, workdir, cfg, log=None, meta=None):
    """Run an argv list (never a shell string) in the sandbox with the workspace mounted read-only and no data.
    The caller validates argv against its allowlist; this only refuses anything that is not a list of plain
    strings. Same limits, timeout (the container is killed, not just abandoned) and result as run_python."""
    if not isinstance(argv, (list, tuple)) or not argv or not all(isinstance(a, str) and a and "\x00" not in a
                                                                  for a in argv):
        raise ValueError(f"argv must be a non-empty list of non-empty strings without NUL, got {argv!r}")
    workdir = Path(workdir).resolve()
    return _run(cfg, lambda s, name: docker_args(s, name, workdir, None, command=list(argv), workspace_mode="ro"),
                b"", log, meta)


def _run(cfg, make_args, stdin_bytes, log, meta):
    """Run one container (make_args(settings, name) gives the docker command line), feeding stdin_bytes.

    Returns {exit_code, stdout, stderr, timed_out, truncated, killed, output_limit_exceeded,
    stdout_bytes, stderr_bytes}. Output is read with a bounded reader: the host keeps at most
    max_output_bytes per stream and drains and discards the rest (stdout_bytes / stderr_bytes report
    how much was produced). If the code produces more than kill_after_output_bytes in total, the
    container is killed early instead of burning its whole timeout.

    After a timeout or output flood, cleanup (kill, remove, waiting for the CLI and the readers) shares
    one budget of cleanup_timeout_s, so a hung Docker daemon cannot stretch the call much past
    timeout_s + cleanup_timeout_s. If removal cannot be confirmed in that budget the result carries
    cleanup_failed=True and a sandbox_cleanup_failed event is logged with the container name."""
    s = settings(cfg)
    ok, reason = status(cfg)
    if not ok:
        if log is not None:
            log.emit("sandbox_refused", reason=reason, **(meta or {}))
        raise SandboxUnavailable(reason)

    name = f"argus-{uuid.uuid4().hex[:12]}"
    args = make_args(s, name)
    limit = int(s["max_output_bytes"])
    kill_after = int(s["kill_after_output_bytes"])
    deadline = time.monotonic() + float(s["timeout_s"])

    flood = threading.Event()
    readers = []

    def on_total():
        if sum(r.total for r in readers) > kill_after:
            flood.set()

    proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    readers.extend([_BoundedReader(proc.stdout, limit, on_total), _BoundedReader(proc.stderr, limit, on_total)])
    feeder = threading.Thread(target=_feed, args=(proc.stdin, stdin_bytes), daemon=True)
    for t in (feeder, *readers):
        t.start()

    timed_out = output_limit = False
    while proc.poll() is None:
        if flood.wait(0.05):
            output_limit = True
            break
        if time.monotonic() >= deadline:
            timed_out = True
            break
    cleanup_deadline = time.monotonic() + float(s["cleanup_timeout_s"])
    cleanup_failed = False
    if timed_out or output_limit:
        _remove(s, name, cleanup_deadline)
        try:
            proc.wait(timeout=_left(cleanup_deadline))
        except subprocess.TimeoutExpired:
            proc.kill()        # the docker CLI process only; its pipes close, so the readers finish
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        _remove(s, name, cleanup_deadline)   # again, in case the container was only created after the first attempt
        cleanup_failed = not _container_gone(s, name, cleanup_deadline)
    for t in (feeder, *readers):
        t.join(timeout=_left(cleanup_deadline))
    if cleanup_failed and log is not None:
        log.emit("sandbox_cleanup_failed", container=name, timed_out=timed_out,
                 output_limit_exceeded=output_limit, cleanup_timeout_s=float(s["cleanup_timeout_s"]),
                 **(meta or {}))

    exit_code = None if timed_out else proc.returncode
    out, err = readers
    result = {"exit_code": exit_code,
              "stdout": _decode(out.kept, out.truncated), "stderr": _decode(err.kept, err.truncated),
              "timed_out": timed_out, "truncated": out.truncated or err.truncated,
              "killed": exit_code == 137 and not output_limit, "output_limit_exceeded": output_limit,
              "stdout_bytes": out.total, "stderr_bytes": err.total, "cleanup_failed": cleanup_failed}
    if log is not None:
        log.emit("sandbox_run", container=name, exit_code=exit_code, timed_out=timed_out,
                 killed=result["killed"], truncated=result["truncated"], output_limit_exceeded=output_limit,
                 stdout_bytes=out.total, stderr_bytes=err.total, cleanup_failed=cleanup_failed, **(meta or {}))
    return result
