"""For one batch draft: writable, the "Why they fail now" block, the drafted tests, and the drafted tests on base + the
maintainers' fix in the sandbox (no model call). Usage: draft_check.py <job id> <instance>"""
import json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, os.path.expanduser("~/Argus-agent"))
from runner import load_config
from acceptance import intake
from acceptance.validation import run_validation
job, iid = sys.argv[1], sys.argv[2]
J = Path.home() / "pilot3a_live" / "jobs" / job
d1 = sorted((J / "runs").glob(f"{job}-d*"))[-1]
draft = json.loads((d1 / "draft.json").read_text())
rev = (d1 / "DRAFT_REVIEW.md").read_text()
c = draft["contract"]
print("writable:", c["scope"]["writable"])
for v in c["validation"]:
    print("validation", v["id"], v.get("environment"), " ".join(v["args"]), "| required:", v.get("must_pass"))
m = re.search(r"Why they fail now.*?```text\n(.*?)```", rev, re.S)
print("---- WHY\n" + (m.group(1) if m else "(not found)") + "----")
print("changed_tests:", [t["path"] for t in draft.get("changed_tests") or []])
inst = Path.home() / "swe" / "inst" / iid
tmp = Path(tempfile.mkdtemp())
os.chmod(tmp, 0o755)               # the sandbox runs as nobody: the workspace root must be readable
intake.write_tree(Path.home() / "swe" / "sympy", (inst / "base_commit.txt").read_text().strip(), tmp, [])
intake.git(tmp, "apply", "--whitespace=nowarn", str(inst / "patch.diff"))
paths = []
for t in list(draft["new_tests"]) + list(draft.get("changed_tests") or []):
    p = tmp / t["path"]; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(t["content"]); paths.append(t["path"])
for t in draft["new_tests"]:
    print(f"==== {t['path']}\n{t['content']}")
cfg = {**(load_config().get("sandbox") or {}), "kind": "docker"}
os.environ["ARGUS_SANDBOX_IMAGE"] = open(os.path.expanduser("~/Argus-agent/.sandbox_image")).read().strip()
os.environ["ARGUS_SANDBOX_IMAGE_SYMPY"] = open(os.path.expanduser("~/Argus-agent/.sandbox_image_sympy")).read().strip()
r = run_validation({"id": "drafter_on_gold", "executable": "python", "args": ["-m", "pytest", *paths], "timeout_s": 600,
                    "min_tests": 1, "max_skipped": 1000, "must_pass": [], "environment": "sympy"}, str(tmp), cfg)
ev = r["evidence"]
print("DRAFTER TESTS ON THE MAINTAINERS' FIX:", r["status"], {k: ev.get(k) for k in ("tests_run", "failures", "errors")},
      r["reason"][:300], ev.get("failed_nodes"))
if r["status"] != "pass": print("OUTPUT TAIL:", (ev.get("output_tail") or "")[-800:], "STDERR:", (ev.get("stderr_tail") or "")[-500:])
shutil.rmtree(tmp)
