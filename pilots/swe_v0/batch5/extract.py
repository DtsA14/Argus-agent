import json, sys
from pathlib import Path
import pyarrow.parquet as pq
want = set(sys.argv[2:])
for r in pq.read_table(sys.argv[1]).to_pylist():
    if r["instance_id"] in want:
        d = Path.home() / "swe" / "inst" / r["instance_id"]
        d.mkdir(parents=True, exist_ok=True)
        for k, f in [("patch", "patch.diff"), ("test_patch", "test_patch.diff"), ("problem_statement", "problem_statement.txt"),
                     ("base_commit", "base_commit.txt"), ("FAIL_TO_PASS", "FAIL_TO_PASS.txt"), ("PASS_TO_PASS", "PASS_TO_PASS.txt")]:
            (d / f).write_text(r[k], encoding="utf-8")
        print(r["instance_id"], r["version"], len(r["problem_statement"]))
