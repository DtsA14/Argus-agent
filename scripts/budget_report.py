"""Print the daily and monthly meters for this machine: `python scripts/budget_report.py [--jobs-dir DIR]`. A convenience for comparing the meters with a provider's dashboard
(SPEC_BUDGET_V2 B1.1): the same numbers as `GET /api/budget`, by platform and by source. Read only; it opens no ledger for writing and calls no model."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from router import budget as bg  # noqa: E402
from runner import load_config  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs-dir", default=str(Path(__file__).resolve().parent.parent / "jobs"))
    o = ap.parse_args()
    lim = bg.settings(load_config())
    if lim is None:
        print("chat.budget is not in the config: the meters are off")
        return 1
    led = bg.Ledgers(o.jobs_dir)
    led.warm(lim["sources"])
    s = led.snapshot(lim)
    for name in ("day", "month"):
        w = s[name]
        print(f"{name} {w['date']} (WIB): " + ("UNKNOWN " + str(w["unknown"]) if w["spent_usd"] is None else f"${w['spent_usd']:.4f} of ${w['limit_usd']:.2f}" + ("  [warning]" if w["warn"] else "")))
        for title, key in (("platform", "by_platform"), ("source", "by_source")):
            for k, v in (w[key] or {}).items():
                print(f"    by {title:8} {k:28} ${v / bg.NANO:9.4f}")
    print(f"files scanned: {s['scanned']}, ignored: {s['ignored']}, missing sources: {[x['label'] for x in s['sources'] if x['missing']]}")
    print(bg.NOTE)
    return 0


sys.exit(main())
