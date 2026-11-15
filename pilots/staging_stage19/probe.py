"""Stage 19 step 5: read-only GETs of /scoreboard/models through the live release's own socket (the way the smoke test talks to it).
Usage: probe.py   (from the Argus-agent checkout; prints one line per check and exits 1 on the first false one)."""
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
c, b = get("/scoreboard/models")
body = json.loads(b)
check("GET /scoreboard/models -> 200", c == 200)
check("keys models, total in that order", list(body) == ["models", "total"], list(body))
check("every entry has model, calls, cost_nano, cost_usd in order", all(list(m) == ["model", "calls", "cost_nano", "cost_usd"] for m in body["models"]))
check("sorted by cost_nano descending then model", body["models"] == sorted(body["models"], key=lambda m: (-m["cost_nano"], m["model"])))
check("total is the sum of the entries", body["total"]["cost_nano"] == sum(m["cost_nano"] for m in body["models"])
      and body["total"]["calls"] == sum(m["calls"] for m in body["models"]))
check("total.cost_nano equals /summary cost_nano", body["total"]["cost_nano"] == summary["cost_nano"], f"{body['total']['cost_nano']} vs {summary['cost_nano']}")
parts = 0
for kind in ("code", "research", "issue"):
    c, b = get(f"/scoreboard/models?kind={kind}")
    k = json.loads(b)
    check(f"?kind={kind} -> 200 with models and total", c == 200 and list(k) == ["models", "total"], f"{k['total']['calls']} calls, {k['total']['cost_nano']} nano")
    parts += k["total"]["cost_nano"]
check("the three kinds add up to the unfiltered total (no job of another kind)", parts == body["total"]["cost_nano"], f"{parts} vs {body['total']['cost_nano']}")
for bad_kind in ("nope", ""):
    c, b = get(f"/scoreboard/models?kind={bad_kind}")
    check(f"?kind={bad_kind!r} -> 400 unknown kind", c == 400 and json.loads(b) == {"detail": f"unknown kind: {bad_kind}"}, b[:80])
c, b = get("/scoreboard/models", host="evil.example")
check("evil.example -> 400", c == 400)
print("RESULT:", "FAIL " + ", ".join(bad) if bad else "all ok")
sys.exit(1 if bad else 0)
