"""Run a general task (slice 1): an agent fixes an issue in a copy of a fixture repository under a frozen contract.

  python scripts/run_code_task.py --contract fixtures/contracts/fix_divide.json --run-id t1
  python scripts/run_code_task.py --contract ... --run-id t1 --resume
  python scripts/run_code_task.py --contract ... --run-id t1 --crash-at agent@after_llm     (crash tests)
  python scripts/run_code_task.py --contract ... --run-id t1 --sandbox docker   (validation in the pinned sandbox)

Validation runs only in the Docker sandbox. Without one (config sandbox.kind none, the default) setup ends the run as
BLOCKED (sandbox_unavailable) before any model call. --sandbox docker sets sandbox.kind for this run; the pinned
image comes from ARGUS_SANDBOX_IMAGE or .sandbox_image (scripts/pin_sandbox_image.sh).

A real model spends money, so a coder model whose provider is not 'fake' needs ARGUS_LIVE=1. Exit codes: 0 DONE,
1 any other final status, 2 refused before starting, 42 a simulated crash.
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from codetask.run import RunExists, run_code_task  # noqa: E402
from models.registry import ConfigError, ModelRef  # noqa: E402
from runner import load_config  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--contract", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--runs-dir", default=str(ROOT / "runs"))
    ap.add_argument("--config", help="config file (default: config.yaml)")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--crash-at", help="simulate a hard crash once at this point (tests)")
    ap.add_argument("--sandbox", choices=["docker"], help="run validation in the Docker sandbox (pinned image)")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)

    cfg = load_config(a.config)
    if a.sandbox:
        cfg["sandbox"] = {**(cfg.get("sandbox") or {}), "kind": a.sandbox}
        if not os.environ.get("ARGUS_SANDBOX_IMAGE") and (ROOT / ".sandbox_image").exists():
            os.environ["ARGUS_SANDBOX_IMAGE"] = (ROOT / ".sandbox_image").read_text().strip()
    ref = ModelRef.parse(cfg["roles"][cfg["code_task"]["role"]]["model"])
    if ref.provider != "fake" and os.environ.get("ARGUS_LIVE") != "1":
        print(f"refused: the coder model {ref} is real and spends money; set ARGUS_LIVE=1", file=sys.stderr)
        return 2
    try:
        r = run_code_task(contract_path=a.contract, run_id=a.run_id, runs_dir=a.runs_dir, cfg=cfg,
                          resume=a.resume, crash_at=a.crash_at, echo=not a.quiet)
    except (RunExists, ConfigError) as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    print(json.dumps({k: r[k] for k in ("status", "stop_reason", "blocked_reason", "attempts", "usd_billed",
                                        "llm_calls")}, ensure_ascii=False))
    return 0 if r["status"] == "DONE" else 1


if __name__ == "__main__":
    sys.exit(main())
