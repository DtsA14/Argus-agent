"""Eval Set v1 end to end in the real sandbox: the reference script must pass the eval and the cheating script must
not, through scripts/run_eval.py. Needs Docker and a pinned image; without them the tests are skipped with
"SANDBOX NOT AVAILABLE", which scripts/verify.sh does not count as passing."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tools import sandbox as sb

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def image():
    ok, reason = sb.status({"kind": "docker"})
    if not ok:
        pytest.skip(f"SANDBOX NOT AVAILABLE: {reason}")
    return sb.settings({})["image"]


def _eval(tmp_path, mode, image):
    env = {**{k: v for k, v in os.environ.items() if k != "ARGUS_LIVE"}, "ARGUS_SANDBOX_IMAGE": image}
    r = subprocess.run([sys.executable, "scripts/run_eval.py", "--mode", mode, "--runs-dir", str(tmp_path / mode)],
                       cwd=ROOT, capture_output=True, text=True, env=env, timeout=900)
    return r, json.loads((tmp_path / mode / "report.json").read_text())


def test_every_reference_script_passes_the_eval(tmp_path, image):
    r, report = _eval(tmp_path, "reference", image)
    assert r.returncode == 0 and report["benchmark_valid"], (r.stdout[-2000:], r.stderr[-2000:])
    assert all(t["eval_pass"] and t["status"] == t["expected"] for t in report["tasks"])
    assert report["agent"]["model"] == "fake:scripted" and len(report["benchmark_sha256"]) == 64


def test_no_wrong_or_cheating_script_passes_the_eval(tmp_path, image):
    r, report = _eval(tmp_path, "wrong", image)
    assert r.returncode == 0 and report["benchmark_valid"], (r.stdout[-2000:], r.stderr[-2000:])
    assert not any(t["eval_pass"] for t in report["tasks"])
    fd = next(t for t in report["tasks"] if t["id"] == "fix_divide")
    assert fd["status"] == "FAILED_ACCEPTANCE" and fd["checks"]["false_claims"]   # caught lying, not just failing
    assert fd["checks"]["protected_changed"] == []                                # the test edit was refused


def test_a_wrong_script_that_passes_is_reported_as_a_broken_benchmark(tmp_path, image):
    # A fixture whose "wrong" script is really a correct solution is a broken benchmark: the runner must say so
    # (benchmark_valid false, exit code 1) instead of counting it as a detected cheat.
    m = json.loads((ROOT / "evals" / "v1" / "manifest.json").read_text(encoding="utf-8"))
    for t in m["tasks"]:
        t["wrong"] = t["reference"]
    broken = tmp_path / "broken_manifest.json"
    broken.write_text(json.dumps(m), encoding="utf-8")
    env = {**{k: v for k, v in os.environ.items() if k != "ARGUS_LIVE"}, "ARGUS_SANDBOX_IMAGE": image}
    r = subprocess.run([sys.executable, "scripts/run_eval.py", "--mode", "wrong", "--manifest", str(broken),
                        "--runs-dir", str(tmp_path / "w")], cwd=ROOT, capture_output=True, text=True, env=env,
                       timeout=900)
    report = json.loads((tmp_path / "w" / "report.json").read_text())
    assert r.returncode == 1 and report["benchmark_valid"] is False, (r.stdout[-1500:], r.stderr[-1500:])
    assert all(t["eval_pass"] and t["benchmark_ok"] is False for t in report["tasks"])
    assert "BROKEN" in r.stdout

