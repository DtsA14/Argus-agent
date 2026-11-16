"""Stage 20 step 5: read-only GETs of /budget/jobs through the live release's own socket (the way the smoke test talks to it).
Usage: probe.py   (from the Argus-agent checkout; prints one line per check and exits 1 if one is false)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from router import stage as sg  # noqa: E402

st = sg.Staging()
release = st.state()["live"]
sock, peer = st.dir(release) / "sock" / "app.sock", st.container_pid(release)
assert peer, "the live release has no container pid"
bad = []


def get(url, host=sg.HOST):
    return sg._get(sock, host, url, peer=peer)


def check(name, ok, detail=""):
    print(("ok   " if ok else "FAIL ") + name + (f": {detail}" if detail else ""))
    if not ok:
        bad.append(name)


c, b = get("/summary")
summary = json.loads(b)
c, b = get("/budget/jobs")
jobs = json.loads(b)
check("GET /budget/jobs -> 200 and a list", c == 200 and isinstance(jobs, list), f"{c} {len(jobs)} jobs")
check("one item per job of /summary", len(jobs) == summary["jobs"], f"{len(jobs)} vs {summary['jobs']}")
check("costs add up to /summary cost_nano", sum(j["cost_nano"] for j in jobs) == summary["cost_nano"], f"{sum(j['cost_nano'] for j in jobs)} vs {summary['cost_nano']}")
check("sorted by cost_nano descending then job id", jobs == sorted(jobs, key=lambda j: (-j["cost_nano"], j["job"])))
base = ["job", "state", "created_at"], ["cost_nano", "cost_usd", "over_80_percent"]
check("keys in the documented order (max_usd only with a cap)", all(
    list(j) == base[0] + (["max_usd"] if "max_usd" in j else []) + base[1] for j in jobs))
check("over_80_percent is true only above 80% of a positive cap (exact)", all(
    j["over_80_percent"] == ("max_usd" in j and isinstance(j["max_usd"], (int, float)) and not isinstance(j["max_usd"], bool)
                            and j["max_usd"] > 0 and 5 * j["cost_nano"] > 4 * j["max_usd"] * 1_000_000_000) for j in jobs))
c, b = get("/budget/jobs?week=2026-W46")
w46 = json.loads(b)
check("?week=2026-W46 -> 200, a subset of the list", c == 200 and all(j in jobs for j in w46), f"{len(w46)} jobs")
check("?week=2026-W46 keeps the order", w46 == [j for j in jobs if j in w46])
for bad_week in ("2026-W54", "2026-44", "2026-W5", "abc"):
    c, b = get("/budget/jobs?week=" + bad_week)
    check(f"?week={bad_week} -> 400 unknown week", c == 400 and json.loads(b) == {"detail": "unknown week: " + bad_week}, f"{c} {b[:60]!r}")
c, b = get("/budget/jobs?week=")
check("?week= (empty) -> 400", c == 400, f"{c}")
c, b = get("/budget/jobs", host="evil.example")
check("Host evil.example -> 400 or 421", c in (400, 421), f"{c}")
print("RESULT:", "FAIL " + ", ".join(bad) if bad else "all ok")
sys.exit(1 if bad else 0)
