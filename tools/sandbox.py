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
  -i                                  the code is sent on stdin; without -i Docker drops stdin and the
                                      container "succeeds" without running anything
The image must be pinned (name@sha256:... or an image id sha256:...), so a run is reproducible and a
changed image changes the tool version used in memo keys.
"""
import os
import shutil
import subprocess
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
    "max_output_bytes": 65536,
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


def _cap(text, limit):
    data = text.encode("utf-8", errors="replace")
    if len(data) <= limit:
        return text, False
    return data[:limit].decode("utf-8", errors="ignore"), True


def docker_args(s, name, workdir, data_dir):
    return [
        s["docker"], "run", "--rm", "-i", "--name", name,
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
        s["image"], "python3", "-I", "-",
    ]


def run_python(code, *, workdir, data_dir, cfg, log=None, meta=None):
    """Run `code` in the sandbox. Returns {exit_code, stdout, stderr, timed_out, truncated, killed}."""
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
    timed_out = False
    try:
        r = subprocess.run(args, input=code, capture_output=True, text=True, timeout=float(s["timeout_s"]))
        exit_code, out, err = r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired as e:
        timed_out = True
        subprocess.run([s["docker"], "kill", name], capture_output=True, timeout=30)
        subprocess.run([s["docker"], "rm", "-f", name], capture_output=True, timeout=30)
        exit_code = None
        out = e.stdout.decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        err = e.stderr.decode(errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
    out, t1 = _cap(out, int(s["max_output_bytes"]))
    err, t2 = _cap(err, int(s["max_output_bytes"]))
    result = {"exit_code": exit_code, "stdout": out, "stderr": err, "timed_out": timed_out,
              "truncated": t1 or t2, "killed": exit_code == 137}
    if log is not None:
        log.emit("sandbox_run", container=name, exit_code=exit_code, timed_out=timed_out,
                 killed=result["killed"], truncated=result["truncated"], **(meta or {}))
    return result
