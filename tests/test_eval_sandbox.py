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



def test_running_an_eval_again_into_the_same_runs_never_reuses_the_old_run(tmp_path, image):
    # Run ids are deterministic (<mode>_<task>), so a second eval into the same runs directory must be refused,
    # never answered from the first run's checkpoint and workspace.
    from codetask.run import RunExists
    from evals import runner as ev
    from runner import load_config
    cfg = load_config()
    cfg["sandbox"] = {"kind": "docker", "image": image}
    manifest = ROOT / "evals" / "v1" / "manifest.json"
    first = ev.run_eval(manifest, "reference", tmp_path / "runs", cfg, tasks=["fix_divide"])
    assert first["tasks"][0]["eval_pass"]
    with pytest.raises(RunExists):
        ev.run_eval(manifest, "reference", tmp_path / "runs", cfg, tasks=["fix_divide"])


def _script_eval(tmp_path, image, first_script):
    """Mode reference over the real manifest, with the first task's script replaced."""
    from evals import runner as ev
    from runner import load_config
    m = json.loads((ROOT / "evals" / "v1" / "manifest.json").read_text(encoding="utf-8"))
    m["tasks"][0]["reference"] = first_script
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(m), encoding="utf-8")
    cfg = load_config()
    cfg["sandbox"] = {"kind": "docker", "image": image}
    return m, ev.run_eval(path, "reference", tmp_path / "runs", cfg)


@pytest.mark.parametrize("status,first_script", [
    ("BLOCKED", [{"error_status": 401, "message": "invalid api key"}]),               # the provider fails
    ("FAILED_BUDGET", [{"tool_calls": [{"name": "ListFiles", "args": {}, "id": "l1"}],  # billed far over the reservation
                        "usage": {"input_tokens": 45000, "output_tokens": 50}}]),
])
def test_an_infrastructure_or_budget_stop_ends_the_eval_and_skips_the_rest(tmp_path, image, status, first_script):
    m, report = _script_eval(tmp_path, image, first_script)
    first, rest = report["tasks"][0], report["tasks"][1:]
    assert first["status"] == status and not first.get("not_run") and first["stats"]["llm_calls"] == 1
    assert report["stopped"]["task"] == m["tasks"][0]["id"] and report["stopped"]["status"] == status
    assert rest and all(r["not_run"] and r["status"] is None and "stopped after" in r["why"][0] for r in rest)
    assert report["ran"] == 1 and report["not_run"] == len(rest) and report["summary"]["total"]["tasks"] == 1
    assert report["usd_spent"] == first["stats"]["usd_billed"] > 0                  # what ran is still paid for
    assert sorted(p.name for p in (tmp_path / "runs").iterdir()) == [f"reference_{m['tasks'][0]['id']}"]
    assert report["benchmark_valid"] is False                                        # fail closed


def test_failed_acceptance_is_data_and_never_stops_the_eval(tmp_path, image):
    lazy = {"tool_calls": [{"name": "Finish", "args": {"claims": [{"claim": "tests_pass",
                                                                   "evidence": "validation:unit"}],
                                                       "summary": "done"}, "id": "f1"}],
            "usage": {"input_tokens": 500, "output_tokens": 60}}
    m, report = _script_eval(tmp_path, image, [lazy, lazy])
    assert report["tasks"][0]["status"] == "FAILED_ACCEPTANCE" and report["stopped"] is None
    assert report["not_run"] == 0 and report["ran"] == len(m["tasks"])


# ---- the search-value experiment (evals/search_v1, outside Eval Set v1) ------------------------------------------

def _search_eval(tmp_path, mode, image):
    env = {**{k: v for k, v in os.environ.items() if k != "ARGUS_LIVE"}, "ARGUS_SANDBOX_IMAGE": image}
    r = subprocess.run([sys.executable, "scripts/run_eval.py", "--mode", mode, "--manifest",
                        str(ROOT / "evals" / "search_v1" / "manifest.json"), "--runs-dir", str(tmp_path / mode)],
                       cwd=ROOT, capture_output=True, text=True, env=env, timeout=900)
    return r, json.loads((tmp_path / mode / "report.json").read_text())


def test_search_value_references_pass_with_search_only_where_the_contract_adds_it(tmp_path, image):
    r, report = _search_eval(tmp_path, "reference", image)
    assert r.returncode == 0 and report["benchmark_valid"], (r.stdout[-2000:], r.stderr[-2000:])
    assert [t["id"] for t in report["tasks"]] == ["ledger_terms_a", "ledger_terms_b", "ledger_terms_c"]
    assert all(t["eval_pass"] and t["status"] == "DONE" for t in report["tasks"])
    base = ["list_files", "read_file", "write_file", "run_validation"]
    for k, tools in (("a", base + ["search_files"]), ("b", base + ["search_files"]), ("c", base)):
        run = tmp_path / "reference" / f"reference_ledger_terms_{k}"
        assert json.loads((run / "result.json").read_text())["tools"] == tools, k
        evs = [json.loads(line) for line in (run / "events.jsonl").read_text().splitlines()]
        assert next(e for e in evs if e["event"] == "tools_effective")["tools"] == tools, k


def test_search_value_shallow_patch_is_caught_only_on_its_issue_fixed_claim(tmp_path, image):
    r, report = _search_eval(tmp_path, "wrong", image)
    assert r.returncode == 0 and report["benchmark_valid"], (r.stdout[-2000:], r.stderr[-2000:])
    for t in report["tasks"]:
        assert not t["eval_pass"] and t["status"] == "FAILED_ACCEPTANCE", t["id"]
        assert [c["claim"] for c in t["checks"]["false_claims"]] == ["issue_fixed"], t["id"]
        assert t["checks"]["fresh_validations"]["validation:unit"]["status"] == "pass", t["id"]
        assert t["checks"]["protected_changed"] == [], t["id"]
