"""Form check of the synthetic RC/GATE cases (PROTOCOL.md section 6, step 2): structure only, the contents are not judged. Usage: python3 check_form.py <cases dir>
A case is a directory with input/, workspace/, case.json and why.md; case.json has the keys of the protocol; the scope globs do not both match one input file;
`expect` has the keys of its mechanism with allowed values; the ids match the directory names."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from acceptance.contract import matches  # noqa: E402  (glob matching only)

ROOT = Path(sys.argv[1])
bad = []
cases = sorted(p for p in ROOT.iterdir() if p.is_dir() and not p.name.startswith("_"))
for d in cases:
    where = d.name
    for need in ("input", "workspace"):
        if not (d / need).is_dir():
            bad.append(f"{where}: missing {need}/")
    if not (d / "why.md").is_file() or not (d / "why.md").read_text(encoding="utf-8").strip():
        bad.append(f"{where}: why.md missing or empty")
    try:
        c = json.loads((d / "case.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        bad.append(f"{where}: case.json unreadable: {e}")
        continue
    for k in ("id", "spec_refs", "what", "contract", "agent", "expect"):
        if k not in c:
            bad.append(f"{where}: case.json lacks {k}")
    if c.get("id") != d.name:
        bad.append(f"{where}: id {c.get('id')!r} differs from the directory name")
    mech = d.name.split("-")[0]
    ex, ag = c.get("expect", {}), c.get("agent", {})
    if mech == "RC":
        if ex.get("decision") not in ("confirmed", "unconfirmed", "blocked"):
            bad.append(f"{where}: expect.decision must be confirmed, unconfirmed or blocked")
    elif mech == "GATE":
        if ex.get("detection") not in ("hit", "clean") or not isinstance(ex.get("terminal"), bool):
            bad.append(f"{where}: expect needs detection hit|clean and terminal true|false")
    else:
        bad.append(f"{where}: the id must start with RC- or GATE-")
    if ag.get("end") not in ("conflict_reported", "finished"):
        bad.append(f"{where}: agent.end must be conflict_reported or finished")
    sc = (c.get("contract") or {}).get("scope") or {}
    if not isinstance(sc.get("writable"), list) or not isinstance(sc.get("protected"), list):
        bad.append(f"{where}: contract.scope needs writable and protected lists")
    else:
        for f in sorted(p for p in (d / "input").rglob("*") if p.is_file()):
            rel = f.relative_to(d / "input").as_posix()
            if matches(rel, sc["writable"]) and matches(rel, sc["protected"]):
                bad.append(f"{where}: input file {rel} matches both writable and protected")
    vals = (c.get("contract") or {}).get("validation")
    if not isinstance(vals, list) or not vals:
        bad.append(f"{where}: contract.validation must be a non-empty list")
    for f in (d / "workspace").rglob("*"):
        if f.is_file() and f.name.endswith(".DELETED") and not (d / "input" / f.relative_to(d / "workspace").as_posix()[:-8]).exists():
            bad.append(f"{where}: {f.name} marks a deletion of a file that is not in input/")
n_rc = sum(1 for d in cases if d.name.startswith("RC-")); n_gate = sum(1 for d in cases if d.name.startswith("GATE-"))
print(f"{len(cases)} cases (RC {n_rc}, GATE {n_gate}); {len(bad)} form problem(s)")
for b in bad:
    print(" -", b)
sys.exit(1 if bad else 0)
