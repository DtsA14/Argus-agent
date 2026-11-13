"""Working time of jobs, from each job's own job.json (stage started_at / ended_at and the state log; second resolution, UTC).
usage: job_times.py <label job-id>...   (pairs)   -> a table; also totals.
Columns: draft, wait (AWAITING_APPROVAL until `approved`: whoever approves, not machine time), agent (all agent stages, retries included),
judge (all judge stages), machine = draft + agent, wall = job created until its last stage ended."""
import datetime as dt
import json
import sys
from pathlib import Path

JOBS = Path("/home/ubuntu/Argus-agent/jobs")


def t(s):
    return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")


def secs(job):
    d = json.loads((JOBS / job / "job.json").read_text())
    st = d["stages"]

    def total(kind):
        return sum((t(s["ended_at"]) - t(s["started_at"])).total_seconds() for s in st.values()
                   if s.get("kind") == kind and s.get("started_at") and s.get("ended_at"))
    wait, ready = 0, None
    for e in d["log"]:
        if e["what"] == "state" and e.get("new") == "AWAITING_APPROVAL":
            ready = t(e["at"])
        elif e["what"] == "approved" and ready:
            wait += (t(e["at"]) - ready).total_seconds()
            ready = None
    ends = [t(s["ended_at"]) for s in st.values() if s.get("ended_at")]
    wall = (max(ends) - t(d["created_at"])).total_seconds() if ends else 0
    draft, agent, judge = total("draft"), total("agent"), total("judge")
    return {"draft": draft, "wait": wait, "agent": agent, "judge": judge, "machine": draft + agent, "wall": wall, "stages": ",".join(st)}


def fmt(s):
    s = int(round(s))
    return f"{s // 60}m{s % 60:02d}s"


if __name__ == "__main__":
    args = sys.argv[1:]
    rows = [(args[i], secs(args[i + 1])) for i in range(0, len(args), 2)]
    print(f"{'job':26} {'draft':>7} {'wait':>7} {'agent':>7} {'judge':>8} {'machine':>8} {'wall':>8}  stages")
    tot = {k: 0 for k in ("draft", "wait", "agent", "judge", "machine", "wall")}
    for label, r in rows:
        print(f"{label:26} {fmt(r['draft']):>7} {fmt(r['wait']):>7} {fmt(r['agent']):>7} {fmt(r['judge']):>8} {fmt(r['machine']):>8} {fmt(r['wall']):>8}  {r['stages']}")
        for k in tot:
            tot[k] += r[k]
    print(f"{'TOTAL':26} {fmt(tot['draft']):>7} {fmt(tot['wait']):>7} {fmt(tot['agent']):>7} {fmt(tot['judge']):>8} {fmt(tot['machine']):>8} {fmt(tot['wall']):>8}")
    n = len(rows) or 1
    print(f"{'MEAN per job':26} {fmt(tot['draft'] / n):>7} {fmt(tot['wait'] / n):>7} {fmt(tot['agent'] / n):>7} {fmt(tot['judge'] / n):>8} {fmt(tot['machine'] / n):>8} {fmt(tot['wall'] / n):>8}")
