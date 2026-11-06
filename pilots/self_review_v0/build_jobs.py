import json, shutil, sys, hashlib
from pathlib import Path
sys.path.insert(0, "/home/ubuntu/Argus-agent")
from acceptance import contract as ct  # noqa
S = Path(sys.argv[1]); src = Path.home() / "pi_jobs/j20261106_170438_f594"
for n in ("a", "b"):
    jid = f"j20261106_200000_sr0{n}"
    dst = Path.home() / "sr_jobs" / jid
    if dst.exists(): shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("*-j1", "JUDGE-*"))
    for old in dst.rglob("*f594*"):
        pass
    runs = dst / "runs"
    for d in sorted(runs.iterdir()):
        d.rename(runs / d.name.replace("j20261106_170438_f594", jid))
    job = json.loads((dst / "job.json").read_text())
    job["job"] = jid
    job["inputs"]["issue"] = (S / "issue.md").read_text()
    job["inputs"]["repo"] = "/home/ubuntu/Argus-agent"; job["inputs"]["commit"] = "b65ec4f8^"
    job["stages"].pop("j1", None)
    draft = {"plan": "Implement the spec in the issue in harness/llm.py and config.yaml (R1-R4); new tests in "
                     "tests/test_rate_limit_retry.py for G1-G8; existing test helpers get the new llm settings.",
             "new_tests": [{"path": "tests/test_rate_limit_retry.py"}],
             "note": "Replay: this is a pull request a human-supervised coding agent made to the Argus harness itself."}
    (runs / f"{jid}-d1" / "draft.json").write_text(json.dumps(draft))
    sha = hashlib.sha256(ct.canonical(draft).encode()).hexdigest()
    job["stages"]["d1"]["draft_sha256"] = sha; job["approval"]["draft_sha256"] = sha
    for k in ("d1", "a1"):
        job["stages"][k]["run_id"] = f"{jid}-{k}"
    job["stages"]["a1"]["review"]["dir"] = str(runs / f"{jid}-a1" / "review")
    rv = runs / f"{jid}-a1" / "review"
    (rv / "changes.patch").write_text((S / "pre_fix.patch").read_text())
    (rv / "claims.md").write_text((S / "claims.md").read_text())
    (rv / "tests.md").write_text("Replay of a merged pull request: the harness did not run tests for this package. "
                                 "The author ran tests/test_rate_limit_retry.py and the non-sandbox suite before review.\n")
    (dst / "job.json").write_text(json.dumps(job, indent=1))
    print(jid, sha[:12])
