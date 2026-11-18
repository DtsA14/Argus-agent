"""`argus t3b-run`: one round of the T3b test of the domain reader (docs/reviews/SPEC_KARTU_SETUJU.md section 8) with an Argus model as the reader, outside the
approval card: the spec is unchanged (the reader of the card is still a Claude session); this only measures how a model of Argus's own reads the sets that
scripts/t3b_fixtures.py planted. The model is the role `code_judge` of the config (GLM-5.3 through OpenRouter, Baidu fp8 pin) with its output limit cut to
`--max-output` for this run, in a copy of the config: config.yaml is not changed.

Every call goes through LLMCaller (a reservation before sending, an entry in the ledger before and after, money in integer nano-dollars). The run has its own
cap (`--cap-usd`): a call starts only if the money already billed plus its worst case fits in the cap, so the cap is never passed. The bundle is data: the
reply is parsed as one JSON object {verdict, sources, note} and nothing else is done with its text. A reply that is not usable, or that the `examples-read` path
refuses (an `ok` that rests on the writer's text alone), is written to the errors file and is not a reading: `score` then says the set has no second reading.

The readings are recorded under the reader id `argus:<model>`; the note files keep the kind `claude` (that is what the path writes), so they are for this test
and never for a card: the approval card reads only the notes of the PRD jobs of the live jobs directory.
"""
import copy
import json
import re
import sys
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from harness.errors import LLMCallFailed
from harness.events import EventLog
from harness.llm import LLMCaller, Reservation, reconcile_ledger
from models.registry import ModelRef, price_for
from router import job as rj

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import t3b_fixtures as t3  # noqa: E402

ROLE = "code_judge"
ERRORS = "t3b_errors.jsonl"
LEDGER = "t3b_ledger.jsonl"
INSTRUCTION = ("You are the domain reader in a test. Follow the instructions inside the bundle you are given (they are your task) and check each example by "
               "arithmetic yourself. Do not run any command and do not use the `argus` command the bundle mentions: the program that started you records your "
               "answer. Reply with ONLY one JSON object on one line: {\"verdict\": \"ok\" or \"concerns\", \"sources\": [\"permintaan Atha\" | "
               "\"dokumen repo: <file>\" | \"hanya tulisan penulis\", ...one per rule behind a number], \"note\": \"at most 500 characters: what you checked and "
               "what you found, with the numbers\"}.")
CHARS_PER_TOKEN = 2.5            # an over-estimate for Indonesian and numbers: a reservation must not be too small
FAILS_IN_A_ROW = 3


def text_of(msg):
    c = msg.content
    if isinstance(c, list):
        c = "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in c)
    return str(c)


def parse_answer(text):
    """(verdict, sources, note) from a reply that holds one JSON object of the asked shape, else None."""
    candidates = [text.strip()]
    fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    candidates += fenced[::-1]
    first, last = text.find("{"), text.rfind("}")
    if 0 <= first < last:
        candidates.append(text[first:last + 1])
    for c in candidates:
        try:
            d = json.loads(c)
        except ValueError:
            continue
        if (isinstance(d, dict) and d.get("verdict") in ("ok", "concerns") and isinstance(d.get("sources"), list)
                and all(isinstance(s, str) for s in d["sources"]) and isinstance(d.get("note"), str) and d["note"].strip()):
            return d["verdict"], d["sources"], d["note"]
    return None


def worst_usd(cfg, ref, in_chars, max_output):
    p = price_for(cfg, ref)
    return (in_chars / CHARS_PER_TOKEN) * p["input"] / 1e6 + max_output * p["output"] / 1e6


def _error(kd, **fields):
    with open(kd / ERRORS, "a", encoding="utf-8") as f:
        f.write(json.dumps(fields, ensure_ascii=False) + "\n")


def run(root, run_no, *, cfg, deps, cap_usd=0.50, max_output=6000, limit=None, model=None):
    """Read the sets of `root` that have no reading `run_no` yet, one call each. Returns a summary dict."""
    root = Path(root)
    kd = t3.keydir(root)
    if run_no not in (1, 2):
        raise rj.Refused("--run is 1 or 2")
    if not (kd / t3.KEY_FILE).exists() or not (root / "jobs").is_dir():
        raise rj.Refused(f"{root} is not a T3b directory built by scripts/t3b_fixtures.py")
    if not (isinstance(cap_usd, (int, float)) and 0 < cap_usd <= 5) or not (isinstance(max_output, int) and 500 <= max_output <= 32000):
        raise rj.Refused("--cap-usd is above 0 and at most 5; --max-output is 500 to 32000")
    done = {(r["job"], r["run"]) for r in t3.read_all(root)}
    todo = [j for j in sorted(p.name for p in (root / "jobs").iterdir()) if (j, run_no) not in done]
    if limit is not None:
        todo = todo[:int(limit)]
    cfg = copy.deepcopy(cfg)
    cfg["roles"][ROLE]["max_output_tokens"] = max_output
    cfg["budget"]["max_usd"] = cap_usd
    ref = ModelRef.parse(cfg["roles"][ROLE]["model"])
    bundles = {j: t3.bundle(root, j) for j in todo}
    worst = {j: worst_usd(cfg, ref, len(INSTRUCTION) + len(bundles[j][0]), max_output) for j in todo}
    biggest = max(worst.values(), default=0.0)
    text = "\n".join([f"T3b reader run {run_no} with {ref} (role {ROLE}), outside the approval card; the spec is unchanged",
                      f"{len(todo)} call(s); output limit {max_output} tokens; worst case per call up to ${biggest:.4f}",
                      f"cap for this run: ${cap_usd:.2f} (a call starts only if billed so far + its worst case fits)",
                      f"ledger: {kd / LEDGER}"])
    summary = {"model": str(ref), "run": run_no, "planned": len(todo), "calls": 0, "recorded": 0, "unusable": 0, "refused": 0, "billed_usd": 0.0,
               "stopped": None}
    if not todo:
        return summary
    with rj.live(deps, cfg, [ROLE], text):
        log = EventLog(kd / LEDGER)
        caller = LLMCaller(cfg, ROLE, log, model=model)
        fails = 0
        for jid in todo:
            billed = reconcile_ledger(log.read())[1]["usd"]
            if billed + worst[jid] > cap_usd:
                summary["stopped"] = f"cost cap: billed ${billed:.6f} + worst case ${worst[jid]:.6f} > ${cap_usd:.2f}"
                break
            res = Reservation(tokens=int(len(bundles[jid][0]) / CHARS_PER_TOKEN) + max_output + 2000, usd=worst[jid])
            try:
                reply = caller.call([SystemMessage(INSTRUCTION), HumanMessage(bundles[jid][0])], res,
                                    meta={"node": "t3b_reader", "task": jid, "iteration": run_no, "step": 0})
            except LLMCallFailed as e:
                fails += 1
                summary["calls"] += 1
                _error(kd, job=jid, run=run_no, why=f"call failed: {type(e).__name__}")
                if fails >= FAILS_IN_A_ROW:
                    summary["stopped"] = f"{fails} failed calls in a row"
                    break
                continue
            fails = 0
            summary["calls"] += 1
            got = parse_answer(text_of(reply))
            if got is None:
                summary["unusable"] += 1
                _error(kd, job=jid, run=run_no, why="the reply is not one JSON object of the asked shape", head=text_of(reply)[:200])
                continue
            verdict, sources, note = got
            try:
                t3.record(root, jid, run_no, bundles[jid][1]["bundle_sha256"], verdict, sources, note, f"argus:{ref}")
                summary["recorded"] += 1
            except (rj.Refused, SystemExit) as e:
                summary["refused"] += 1
                _error(kd, job=jid, run=run_no, why=f"the examples-read path refused the reading: {e}", verdict=verdict, sources=sources)
        summary["billed_usd"] = reconcile_ledger(log.read())[1]["usd"]
    return summary
