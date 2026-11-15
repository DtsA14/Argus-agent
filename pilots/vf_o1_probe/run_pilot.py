"""Non-strict pilot of the GREEN script in the sandbox, per environment (SPEC_VF_O1_CANARY_NONCE section 4b). Run with the image pins
exported (see scripts/precheck.sh). Prints one line per (environment, case)."""
import json, shutil, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from acceptance import validation as va
from runner import load_config
from tools import sandbox as sb

HERE = Path(__file__).parent
GREEN = (HERE / "green_v2.py").read_text()
NONCE = "ARGUS-GREEN-pilot0000000000000000000000:"


def workspace(case):
    ws = Path(tempfile.mkdtemp(prefix="vfpilot_"))
    if case == "honest_mix":
        shutil.copytree(HERE / "honest_mix", ws, dirs_exist_ok=True)
        return ws, "tests/test_mix.py"
    base = ROOT / "fixtures/forgers/pytest_pipe_forger"
    shutil.copytree(base, ws, dirs_exist_ok=True)
    over = {"pipe_forger": None, "noop_forger": HERE / "noop_forger/src/app.py", "f1": HERE / "path_forger_f1/src/app.py",
            "f2": HERE / "session_forger_f2/src/app.py"}[case]
    if over:
        shutil.copy(over, ws / "src/app.py")
        (ws / "src/__init__.py").touch()
    return ws, "tests/test_new.py"


def strip(text):
    lines = [l for l in text.splitlines() if not l.startswith(NONCE)]
    recs = [json.loads(l[len(NONCE):]) for l in text.splitlines() if l.startswith(NONCE)]
    return "\n".join(lines), recs


def main(envs):
    base = {**(load_config().get("sandbox") or {}), "kind": "docker", "memory": "512m", "timeout_s": 120}
    for env in envs:
        cfg = {**base, "environment": env}
        ok, why = sb.status(cfg)
        if not ok:
            print(env, "UNAVAILABLE", why); continue
        for case in ("honest_mix", "pipe_forger", "noop_forger", "f1", "f2"):
            ws, target = workspace(case)
            argv = ["python3", "-I", "-B", "-c", GREEN, NONCE, target]
            r = sb.run_command(argv, workdir=str(ws), cfg=cfg)
            text, recs = strip(r.get("stdout") or "")
            parsed = va.parse_pytest(text)
            verdict = []
            if len(recs) != 1:
                verdict.append(f"no/odd record ({len(recs)})")
            else:
                rec = recs[0]
                want = {"test_pass": "ok", "test_fail": "FAIL:AssertionError", "test_error": "FAIL:RuntimeError"}
                got = {k: rec["canary"].get(k) for k in want}
                if got != want:
                    verdict.append(f"canary {got}")
                if rec["rc"] != r.get("exit_code"):
                    verdict.append("rc differs")
                import hashlib
                pairs = sorted([n, s] for n, s in parsed["tests"].items())
                sha = hashlib.sha256(json.dumps(pairs, ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()
                if sha != rec["sha"]:
                    verdict.append("sha differs")
                    verdict.append("record=" + json.dumps(rec["counts"]) + " text=" + json.dumps(
                        {s: list(parsed["tests"].values()).count(s) for s in set(parsed["tests"].values())}))
            print(f"{env:18} {case:12} consistent={parsed['consistent']} exit={r.get('exit_code')} "
                  f"=> {'FAIL: ' + '; '.join(verdict) if verdict else 'PASS'}")
            shutil.rmtree(ws, ignore_errors=True)


if __name__ == "__main__":
    main(sys.argv[1:] or ["argus", "ledger_py312_up2", "sympy_py39"])
