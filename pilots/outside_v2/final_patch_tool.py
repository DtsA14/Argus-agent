"""Approve on the FINAL patch, with a blind spot check (Fable's order 2026-11-13, item 2; PROTOCOL_FINAL_PATCH.md). Not part of the harness.

  seal     <batch_dir>                    record the sha256 of verdicts_claude.json (Claude's verdicts on the final patches) in SEALED.json
  pick     <batch_dir> <nonce>            refuses unless the verdicts file still matches its seal and both files are committed and unchanged in git;
                                          picks ceil(n/3) of the jobs that have a valid final patch, by a seed made from the final patches' sha256, the
                                          sealed verdicts' sha256 and a nonce Atha writes AFTER the seal is committed (so whoever writes the verdicts
                                          cannot know the sample, and the verdicts alone cannot steer it), and writes packet/ (issue, final patch,
                                          tests.md; no verdict, no judge, no grade, a random code per job) and packet_key.json (code -> label, nonce,
                                          seed; not shown to Atha)
  compare  <batch_dir>                    reads atha_verdicts.json {code: "approve"|"reject"}, prints how many were read and how many Claude's sealed verdict
                                          disagrees with; for the others the line is "0 human minutes, approved by the model"

<batch_dir> holds jobs.json {label: job id} and (after the jobs) verdicts_claude.json
{label: {"verdict": "approve"|"reject", "reason": "<one line>", "read": "final patch", "human_minutes": 0}}; a job whose last review
package is not valid (REVIEW_INVALID) has no final patch to read and gets {"verdict": "no final patch"} instead, and is never sampled.
Jobs are read from <repo>/jobs/<job>/ (job.json, runs/<job>-a*/review/).
"""
import hashlib
import json
import math
import random
import subprocess
import sys
from pathlib import Path

JOBS = Path(__file__).resolve().parents[2] / "jobs"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


NO_PATCH = "no final patch"


def final_review_dir(job):
    dirs = sorted((JOBS / job / "runs").glob(f"{job}-a*/review"), key=lambda p: int(p.parent.name.rsplit("-a", 1)[1]))
    if not dirs:
        raise SystemExit(f"job {job}: no review package")
    return dirs[-1]


def has_final_patch(job):
    """The job's last agent stage built a VALID review package (the state machine moved it to REVIEW_READY, not REVIEW_INVALID)."""
    stages = json.loads((JOBS / job / "job.json").read_text(encoding="utf-8")).get("stages") or {}
    reviews = [st["review"] for st in stages.values() if st.get("review")]
    return bool(reviews) and bool(reviews[-1].get("valid"))


def committed(batch, *names):
    """Each file is tracked by git and identical to HEAD (so its commit, with its timestamp, exists)."""
    for name in names:
        path = batch / name
        r = subprocess.run(["git", "log", "-1", "--format=%H", "--", path.name], cwd=batch, capture_output=True, text=True)
        if r.returncode or not r.stdout.strip():
            return False
        if subprocess.run(["git", "diff", "--quiet", "HEAD", "--", path.name], cwd=batch).returncode:
            return False
    return True


def load(batch, name):
    return json.loads((batch / name).read_text(encoding="utf-8"))


def seal(batch):
    v = load(batch, "verdicts_claude.json")
    jobs = load(batch, "jobs.json")
    if set(v) != set(jobs):
        raise SystemExit(f"verdicts for {sorted(set(jobs) ^ set(v))} are missing or extra: one verdict per job")
    bad, wrong = [], []
    for k, x in v.items():
        valid = has_final_patch(jobs[k])
        if not valid:
            if x.get("verdict") != NO_PATCH:
                wrong.append(k)
        elif x.get("verdict") not in ("approve", "reject") or x.get("read") != "final patch" or x.get("human_minutes") != 0 \
                or not x.get("reason"):
            bad.append(k)
    if wrong:
        raise SystemExit(f"no valid final patch (REVIEW_INVALID), so the verdict must be {NO_PATCH!r}: {wrong}")
    if bad:
        raise SystemExit(f"verdict malformed (verdict approve|reject, reason, read 'final patch', human_minutes 0): {bad}")
    (batch / "SEALED.json").write_text(json.dumps({"verdicts_claude.json": sha(batch / "verdicts_claude.json")}, indent=1) + "\n")
    print("sealed:", sha(batch / "verdicts_claude.json"), "- commit SEALED.json before running `pick`")


def sealed_ok(batch):
    try:
        return load(batch, "SEALED.json")["verdicts_claude.json"] == sha(batch / "verdicts_claude.json")
    except (OSError, KeyError, ValueError):
        return False


def pick(batch, nonce):
    if not sealed_ok(batch):
        raise SystemExit("refused: verdicts_claude.json is not sealed, or changed after the seal")
    if not committed(batch, "verdicts_claude.json", "SEALED.json"):
        raise SystemExit("refused: commit verdicts_claude.json and SEALED.json first, then have Atha choose the nonce")
    if not nonce.strip():
        raise SystemExit("refused: the nonce is empty; Atha writes it after the seal is committed")
    if (batch / "packet_key.json").exists() and load(batch, "packet_key.json").get("nonce") != nonce:
        raise SystemExit("refused: a sample was already picked with another nonce; a second nonce would let the picker choose the sample")
    jobs = {k: j for k, j in load(batch, "jobs.json").items() if has_final_patch(j)}
    if not jobs:
        raise SystemExit("no job has a valid final patch")
    patches = {label: sha(final_review_dir(job) / "changes.patch") for label, job in sorted(jobs.items())}
    lines = [f"{k}:{v}" for k, v in patches.items()] + [f"sealed:{sha(batch / 'verdicts_claude.json')}", f"nonce:{nonce}"]
    seed = hashlib.sha256("\n".join(lines).encode()).hexdigest()
    rng = random.Random(int(seed, 16))
    chosen = rng.sample(sorted(jobs), math.ceil(len(jobs) / 3))
    codes = [f"R{i + 1:02d}" for i in range(len(chosen))]
    rng.shuffle(codes)
    out = batch / "packet"
    out.mkdir(exist_ok=True)
    for old in out.glob("R*.md"):                       # a packet from an earlier pick must not linger beside this one
        old.unlink()
    key = {}
    for code, label in zip(codes, chosen):
        job = jobs[label]
        rd = final_review_dir(job)
        data = json.loads((JOBS / job / "job.json").read_text(encoding="utf-8"))
        parts = [f"# {code}\n\nWould you apply this final patch exactly as it is, without changing a single line? Read the issue, then the patch, then the tests; answer approve or reject. A patch that only needs tidying (file mode, test location, an exception wrapper) is reject.\n",
                 "## Issue\n\n" + data["inputs"]["issue"], "## Final patch (changes.patch)\n\n```diff\n" + (rd / "changes.patch").read_text(encoding="utf-8") + "\n```"]
        if (rd / "tests.md").exists():
            parts.append("## tests.md\n\n" + (rd / "tests.md").read_text(encoding="utf-8"))
        (out / f"{code}.md").write_text("\n\n".join(parts) + "\n", encoding="utf-8")
        key[code] = label
    (batch / "packet_key.json").write_text(json.dumps({"codes": key, "nonce": nonce, "seed": seed}, indent=1) + "\n")
    print(f"seed {seed[:12]}; {len(chosen)} of {len(jobs)} for Atha: packet/{{{','.join(sorted(key))}}}.md (key in packet_key.json: do not show)")


def compare(batch):
    if not sealed_ok(batch):
        raise SystemExit("refused: verdicts_claude.json is not sealed, or changed after the seal")
    mine, key, theirs = load(batch, "verdicts_claude.json"), load(batch, "packet_key.json")["codes"], load(batch, "atha_verdicts.json")
    if set(theirs) != set(key):
        raise SystemExit(f"atha_verdicts.json must answer exactly {sorted(key)}")
    flipped = [(c, key[c], mine[key[c]]["verdict"], theirs[c]) for c in sorted(key) if mine[key[c]]["verdict"] != theirs[c]]
    for c, label, m, a in flipped:
        print(f"FLIPPED {c} ({label}): Claude {m}, Atha {a}")
    with_patch = sum(1 for x in mine.values() if x["verdict"] != NO_PATCH)
    print(f"Atha read {len(key)} of {with_patch} final patches blind ({len(mine) - with_patch} jobs had no final patch); {len(flipped)} flipped. "
          f"Per job, human cost: 0 human minutes, approved by the model (Atha's reading of the {len(key)} is the check, counted apart).")


if __name__ == "__main__":
    cmd, args = (sys.argv[1], sys.argv[2:]) if len(sys.argv) >= 3 else ("", [])
    if cmd == "pick" and len(args) == 2:
        pick(Path(args[0]), args[1])
    elif cmd in ("seal", "compare") and len(args) == 1:
        {"seal": seal, "compare": compare}[cmd](Path(args[0]))
    else:
        sys.exit(__doc__)
