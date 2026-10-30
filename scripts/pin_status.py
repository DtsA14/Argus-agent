"""The sandbox image each environment is pinned to in this checkout, whether Docker has it, and whether it passed its
check: the preflight before a live job (PENDING 2026-10-30: job 001 was refused once because ~/pilot3a_live had no
.sandbox_image_pwa_node22, and verify.sh writes new pins only in the checkout it runs in).

  pin_status.py [--against DIR] [ENV ...]

Without ENV every configured environment is listed. --against compares this checkout's .sandbox_image_<env> files with
DIR's. Exit 1 when a listed environment cannot be used here (no pin, image missing, check not passed) or, with --against,
is pinned differently; 0 otherwise. Reads only: nothing is built, copied or pulled."""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from approve_draft import sandbox_cfg  # noqa: E402  (sets the pins from this checkout's .sandbox_image_* files)
from router.job import environment_pin  # noqa: E402
from runner import load_config  # noqa: E402


def pin_file(root, name):
    p = Path(root) / f".sandbox_image_{name}"
    return p.read_text().strip() if p.is_file() else None


def docker_has(image):
    r = subprocess.run(["docker", "image", "inspect", "--format", "{{.Id}}", image], capture_output=True, text=True)
    return r.returncode == 0


def rows(names, cfg, against=None):
    """[(name, image or None, problem or None)] for each environment, the problem saying why it cannot be used."""
    out = []
    for name in names:
        image, problem = environment_pin(cfg, name, ROOT)
        if image and not docker_has(image):
            problem = f"Docker has no image {image[:19]}"
        if not problem and against is not None and pin_file(against, name) != pin_file(ROOT, name):
            theirs = pin_file(against, name)
            problem = f"pinned differently in {against}: {theirs[:19] if theirs else 'no pin there'}"
        out.append((name, image, problem))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--against", help="another checkout whose .sandbox_image_* files must be the same")
    ap.add_argument("env", nargs="*")
    a = ap.parse_args(argv)
    cfg = {**load_config(), "sandbox": sandbox_cfg()}
    known = list((cfg["sandbox"].get("environments") or {}))
    names = a.env or known
    unknown = [n for n in names if n not in known]
    if unknown:
        print(f"unknown environment(s): {', '.join(unknown)}; configured: {', '.join(known)}", file=sys.stderr)
        return 2
    bad = 0
    for name, image, problem in rows(names, cfg, a.against):
        bad += problem is not None
        print(f"{'ok  ' if problem is None else 'FAIL'} {name:<22} {image[:19] if image else '-':<19}  {problem or ''}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
