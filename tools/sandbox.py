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


def docker_args(s, name, workdir, data_dir):
    return [
        s["docker"], "run", "--rm", "-i", "--name", name, "--label", "argus.sandbox=1",
        "--network", "none",
        "--read-only", "--tmpfs", f"/tmp:rw,size={s['tmpfs_size']},mode=1777",
        "--user", "65534:65534",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--memory", s["memory"], "--memory-swap", s["memory"],
        "--cpus", str(s["cpus"]), "--pids-limit", str(s["pids"]),
        "-v", f"{workdir}:/workspace:rw", "-v", f"{data_dir}:/data:ro",
        "-w", "/workspace",
        "--env", "PYTHONDONTWRITEBYTECODE=1",
        "--log-driver", "none",
        s["image"], "python3", "-I", "-",
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


def _remove(s, name):
    for cmd in (["kill", name], ["rm", "-f", name]):
        try:
            subprocess.run([s["docker"], *cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            pass


def run_python(code, *, workdir, data_dir, cfg, log=None, meta=None):
    """Run `code` in the sandbox.

    Returns {exit_code, stdout, stderr, timed_out, truncated, killed, output_limit_exceeded,
    stdout_bytes, stderr_bytes}. Output is read with a bounded reader: the host keeps at most
    max_output_bytes per stream and drains and discards the rest (stdout_bytes / stderr_bytes report
    how much was produced). If the code produces more than kill_after_output_bytes in total, the
    container is killed early instead of burning its whole timeout."""
    s = settings(cfg)
    ok, reason = status(cfg)
    if not ok:
        if log is not None:
            log.emit("sandbox_refused", reason=reason, **(meta or {}))
        raise SandboxUnavailable(reason)

    workdir, data_dir = Path(workdir).resolve(), Path(data_dir).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    os.chmod(workdir, 0o777)   # the container runs as nobody (65534); this directory is its only writable place
    name = f"argus-{uuid.uuid4().hex[:12]}"
    args = docker_args(s, name, workdir, data_dir)
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
    feeder = threading.Thread(target=_feed, args=(proc.stdin, code.encode("utf-8")), daemon=True)
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
    if timed_out or output_limit:
        _remove(s, name)
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        _remove(s, name)       # again, in case the container was only created after the first attempt
    for t in (feeder, *readers):
        t.join(timeout=30)

    exit_code = None if timed_out else proc.returncode
    out, err = readers
    result = {"exit_code": exit_code,
              "stdout": _decode(out.kept, out.truncated), "stderr": _decode(err.kept, err.truncated),
              "timed_out": timed_out, "truncated": out.truncated or err.truncated,
              "killed": exit_code == 137 and not output_limit, "output_limit_exceeded": output_limit,
              "stdout_bytes": out.total, "stderr_bytes": err.total}
    if log is not None:
        log.emit("sandbox_run", container=name, exit_code=exit_code, timed_out=timed_out,
                 killed=result["killed"], truncated=result["truncated"], output_limit_exceeded=output_limit,
                 stdout_bytes=out.total, stderr_bytes=err.total, **(meta or {}))
    return result
