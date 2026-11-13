"""Approve on the FINAL patch, with a blind spot check (Fable's order 2026-11-13, item 2; PROTOCOL_FINAL_PATCH.md). Not part of the harness.

  seal     <batch_dir>                    record the sha256 of verdicts_claude.json (Claude's verdicts on the final patches) in SEALED.json
  pick     <batch_dir>                    refuses unless the verdicts file still matches its seal; picks ceil(n/3) jobs for Atha, by a seed made from the
                                          final patches' own sha256 (not from any verdict), and writes packet/ (issue, final patch, tests.md; no verdict,
                                          no judge, no grade, a random code per job) and packet_key.json (code -> label; not shown to Atha)
  compare  <batch_dir>                    reads atha_verdicts.json {code: "approve"|"reject"}, prints how many were read and how many Claude's sealed verdict
                                          disagrees with; for the others the line is "0 human minutes, approved by the model"

<batch_dir> holds jobs.json {label: job id} and (after the jobs) verdicts_claude.json
{label: {"verdict": "approve"|"reject", "reason": "<one line>", "read": "final patch", "human_minutes": 0}}.
Jobs are read from <repo>/jobs/<job>/ (job.json, runs/<job>-a*/review/).
"""
import hashlib
import json
import math
import random
import sys
from pathlib import Path

JOBS = Path(__file__).resolve().parents[2] / "jobs"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def final_review_dir(job):
    dirs = sorted((JOBS / job / "runs").glob(f"{job}-a*/review"), key=lambda p: int(p.parent.name.rsplit("-a", 1)[1]))
    if not dirs:
        raise SystemExit(f"job {job}: no review package")
    return dirs[-1]


def load(batch, name):
    return json.loads((batch / name).read_text(encoding="utf-8"))


def seal(batch):
    v = load(batch, "verdicts_claude.json")
    jobs = load(batch, "jobs.json")
    if set(v) != set(jobs):
        raise SystemExit(f"verdicts for {sorted(set(jobs) ^ set(v))} are missing or extra: one verdict per job")
    bad = [k for k, x in v.items() if x.get("verdict") not in ("approve", "reject") or x.get("read") != "final patch"
           or x.get("human_minutes") != 0 or not x.get("reason")]
    if bad:
        raise SystemExit(f"verdict malformed (verdict approve|reject, reason, read 'final patch', human_minutes 0): {bad}")
    (batch / "SEALED.json").write_text(json.dumps({"verdicts_claude.json": sha(batch / "verdicts_claude.json")}, indent=1) + "\n")
    print("sealed:", sha(batch / "verdicts_claude.json"), "- commit SEALED.json before running `pick`")


def sealed_ok(batch):
    try:
        return load(batch, "SEALED.json")["verdicts_claude.json"] == sha(batch / "verdicts_claude.json")
    except (OSError, KeyError, ValueError):
        return False


def pick(batch):
    if not sealed_ok(batch):
        raise SystemExit("refused: verdicts_claude.json is not sealed, or changed after the seal")
    jobs = load(batch, "jobs.json")
    patches = {label: sha(final_review_dir(job) / "changes.patch") for label, job in sorted(jobs.items())}
    seed = hashlib.sha256("\n".join(f"{k}:{v}" for k, v in patches.items()).encode()).hexdigest()
    rng = random.Random(int(seed, 16))
    chosen = rng.sample(sorted(jobs), math.ceil(len(jobs) / 3))
    codes = [f"R{i + 1:02d}" for i in range(len(chosen))]
    rng.shuffle(codes)
    out = batch / "packet"
    out.mkdir(exist_ok=True)
    key = {}
    for code, label in zip(codes, chosen):
        job = jobs[label]
        rd = final_review_dir(job)
        data = json.loads((JOBS / job / "job.json").read_text(encoding="utf-8"))
        parts = [f"# {code}\n\nIs this final patch one you would apply? Read the issue, then the patch, then the tests; answer approve or reject.\n",
                 "## Issue\n\n" + data["inputs"]["issue"], "## Final patch (changes.patch)\n\n```diff\n" + (rd / "changes.patch").read_text(encoding="utf-8") + "\n```"]
        if (rd / "tests.md").exists():
            parts.append("## tests.md\n\n" + (rd / "tests.md").read_text(encoding="utf-8"))
        (out / f"{code}.md").write_text("\n\n".join(parts) + "\n", encoding="utf-8")
        key[code] = label
    (batch / "packet_key.json").write_text(json.dumps(key, indent=1) + "\n")
    print(f"seed {seed[:12]}; {len(chosen)} of {len(jobs)} for Atha: packet/{{{','.join(sorted(key))}}}.md (key in packet_key.json: do not show)")


def compare(batch):
    if not sealed_ok(batch):
        raise SystemExit("refused: verdicts_claude.json is not sealed, or changed after the seal")
    mine, key, theirs = load(batch, "verdicts_claude.json"), load(batch, "packet_key.json"), load(batch, "atha_verdicts.json")
    if set(theirs) != set(key):
        raise SystemExit(f"atha_verdicts.json must answer exactly {sorted(key)}")
    flipped = [(c, key[c], mine[key[c]]["verdict"], theirs[c]) for c in sorted(key) if mine[key[c]]["verdict"] != theirs[c]]
    for c, label, m, a in flipped:
        print(f"FLIPPED {c} ({label}): Claude {m}, Atha {a}")
    print(f"Atha read {len(key)} of {len(mine)} final patches blind; {len(flipped)} flipped. "
          f"Per job, human cost: 0 human minutes, approved by the model (Atha's reading of the {len(key)} is the check, counted apart).")


if __name__ == "__main__":
    cmd, batch = (sys.argv[1], Path(sys.argv[2])) if len(sys.argv) == 3 else ("", None)
    {"seal": seal, "pick": pick, "compare": compare}.get(cmd, lambda b: sys.exit(__doc__))(batch)
