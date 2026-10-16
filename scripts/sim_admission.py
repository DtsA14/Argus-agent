"""Admission of attempts 2 and 3 under a $1.00 run cap at 30k and 45k, using the harness's own settings() and
admission() on synthetic ledgers. Run from the repository root on the VM with PYTHONPATH=."""
import json
import glob
import tempfile
from pathlib import Path

from codetask.run import admission, settings
from harness.events import EventLog
from runner import load_config

NANO = 1_000_000_000
contract = json.loads(Path("fixtures/contracts/ledger_terms_a.json").read_text())
contract["limits"]["max_usd"] = 1.00


def lim_for(tokens):
    cfg = load_config()
    cfg["roles"]["coder"]["model"] = "anthropic:claude-sonnet-5-5"
    cfg["code_task"]["attempt_tokens"] = tokens
    cfg["budget"]["max_usd"] = 1.00
    return settings(cfg, contract)


def admitted(lim, spends):
    """Is one more attempt admitted after attempts that spent `spends` (USD) according to the ledger?"""
    with tempfile.TemporaryDirectory() as t:
        log = EventLog(Path(t) / "e.jsonl")
        for i, usd in enumerate(spends):
            log.emit("llm_call_started", call_id=f"c{i}", node="agent", task="x", iteration=i, step=0,
                     worst_tokens=1, worst_usd_nano=int(usd * NANO))
            log.emit("llm_call", call_id=f"c{i}", status="ok", node="agent", task="x", iteration=i, step=0,
                     tokens=1000, usd_nano=int(usd * NANO))
        return admission(log, lim) is None


for tokens in (30000, 45000):
    lim = lim_for(tokens)
    r = lim["attempt_usd"]
    # the largest total spent by earlier attempts that still admits one more attempt (to the cent)
    edge = max(c / 100 for c in range(0, 101) if admitted(lim, [c / 100]))
    print(f"{tokens}: reservation per attempt ${r:.2f}; one more attempt admitted while spent <= ${edge:.2f} "
          f"(cap {lim['max_usd']:.2f}); max_tokens {lim['max_tokens']}")
    for label, per in (("typical (series #2, ~$0.06 per 30k attempt, scaled)", 0.06 * tokens / 30000),
                       ("plausible maximum (every token used, 5% output)", tokens * (0.95 * 2 + 0.05 * 10) / 1e6),
                       ("pathological (every token billed at the output price)", tokens * 10 / 1e6)):
        a2, a3 = admitted(lim, [per]), admitted(lim, [per, per])
        print(f"   {label}: ${per:.3f} per attempt -> attempt 2 {'yes' if a2 else 'NO'}, "
              f"attempt 3 {'yes' if a3 else 'NO'}")

print("series #2, actual spend per attempt (USD), and whether a 3rd attempt at 45k would be admitted:")
for d in sorted(glob.glob("verification/search-live-2/0*")):
    evs = [json.loads(l) for l in open(d + "/events.jsonl")]
    per = {}
    for e in evs:
        if e["event"] == "llm_call" and e.get("status") == "ok":
            per[e["iteration"]] = per.get(e["iteration"], 0) + e["usd_nano"] / NANO
    spends = [round(per[i] * 1.5, 4) for i in sorted(per)]          # 45k: up to 1.5x the tokens of 30k
    print(f"   {d[-5:]}: 30k {[round(v, 4) for v in per.values()]}  scaled to 45k {spends} -> 3rd admitted "
          f"{admitted(lim_for(45000), spends[:2])}")
