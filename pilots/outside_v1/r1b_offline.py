"""R1b offline on the batch 2 patches (SPEC_REPRO_PATCHED section 6): the issue example run on the base tree and on the base tree with the
job's patch applied, with the harness's own functions (acceptance.repro.run / run_patched / label), next to the blind grade.
No model, no money; it runs agent-written code in the job's sandbox environment, like R1. Not part of the harness.

Usage: python pilots/outside_v1/r1b_offline.py   (from the repo root, with .venv-verify)   -> r1b_offline.json and a table on stdout.
Both runs are done here (the jobs predate R1b and have no repro_patched file); the base result is run again too, so the pair is from the same moment.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from acceptance import repro  # noqa: E402
from approve_draft import sandbox_cfg  # noqa: E402  (the harness's own: kind docker and the .sandbox_image_<env> pins)

HERE = Path(__file__).resolve().parent
JOBS = ROOT / "jobs"
LABEL_JOB = {   # label -> job id (from run_grade.py)
    "mi-1284": "j20261113_011018_89e5", "mi-1277": "j20261113_012156_3af4", "mi-1257": "j20261113_012640_fa75",
    "bo-393": "j20261113_013152_6552", "bo-322": "j20261113_014406_c297", "mi-1304c": "j20261113_014810_75fb",
    "mi-1344c": "j20261113_015507_ddab", "bo-383c": "j20261113_020714_71a4",
}


def patch_of(job):
    ps = sorted((JOBS / job / "runs").glob(f"{job}-a*/review/changes.patch"))
    return ps[-1] if ps else None


def main():
    cfg = {"sandbox": sandbox_cfg()}
    grades = json.loads((HERE / "blind_grades_batch2.json").read_text())
    rows = []
    for label, job in LABEL_JOB.items():
        data = json.loads((JOBS / job / "job.json").read_text())
        issue = data["inputs"]["issue"]
        env = data["inputs"].get("environment")
        scfg = {**(cfg.get("sandbox") or {}), **({"environment": env} if env else {})}
        tree = JOBS / job / "root" / "fixtures" / "repos" / "base"
        patch = patch_of(job)
        base = repro.run(tree, issue, scfg) if tree.is_dir() else None
        patched = repro.run_patched(tree, patch, issue, scfg) if patch and tree.is_dir() else None
        if base is None or patched is None:
            print(f"{label}: NOT RUN (base {'ok' if base is not None else 'None'}, patched {'ok' if patched is not None else 'None'})")
        labels = repro.label(base, patched)
        rows.append({"label": label, "job": job, "grade": grades.get(label), "blocks": len(base or []), "labels": labels,
                     "base": [repro._desc(r) for r in (base or [])], "patched": [repro._desc(r) for r in (patched or [])]})
        print(f"{label:9} grade={grades.get(label)} blocks={len(base or [])} labels={labels}", flush=True)
        for i, (b, p) in enumerate(zip(rows[-1]["base"], rows[-1]["patched"])):
            print(f"            [{i}] base: {b}  ->  patched: {p}")
    (HERE / "r1b_offline.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
