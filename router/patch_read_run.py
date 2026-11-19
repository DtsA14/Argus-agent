"""`argus patch-read-run <job>`: the patch reader of an Argus job is a pair of models of Argus's own (docs/reviews/SPEC_KARTU_SETUJU.md 13.5), not a Claude session.

The first reader is Tencent Hy4 Flash. Only when it says `ok` is the second asked, DeepSeek V4.1 Flash 1017; the patch is `ok` only when both said `ok` (a `concerns` of
either closes it, and a `concerns` of the first needs no second call). Each is given the fixed template of router/patch_read.py, the issue of the job, the files the patch
touches and the patch, as data, and nothing else; the reply must be one JSON object {verdict, note}. Every call goes through LLMCaller (a reservation before sending, an
entry in the ledger before and after, integer nano-dollars) and the cap of the run (`--cap-usd`) is TOTAL for the job's patch readings: the ledger sits in the job
directory (`patch_read_ledger.jsonl`) and a call starts only if the money already billed plus its worst case fits. The readings are written through
`patch_read.record` (reader kind `argus`, id `argus:<model>`), so the card and `argus apply` read them like any note; nothing is added to the log of the job.

The card says what this is: statements of two models, not a proof that the patch was read, and not a human. The pair counts as TESTED only for these two models and
this template (`verification/reader_tests.json`, written by `python -m router.patch_trial write-tests` after a passing trial).
A reply that is not usable (not the asked JSON, cut at the output limit, an error) is not a reading: nothing is written and the run says so."""
import hashlib
import json
import re
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from harness.errors import LLMCallFailed, ReservationExhausted
from harness.events import EventLog
from harness.llm import LLMCaller, is_truncated, reconcile_ledger
from router import job as rj
from router import patch_read as pr
from router import patch_trial as pt
from router import t3b_run as tr

LEDGER = "patch_read_ledger.jsonl"
FIRST, SECOND = "hy4flash", "ds1017"                 # names of router.patch_trial.MODELS: the pair that passed the trial
FILES_MAX = 40
DIFF_FILE = re.compile(r"^\+\+\+ b/(.+)$", re.M)


def reader_id(name):
    return f"argus:{pt.MODELS[name][0]}"


def package(job_id, jobs_dir):
    """(job, sid, sha, patch text, issue): the patch the review recorded, checked like `record` checks it; Refused otherwise."""
    job = rj.open_job(job_id, jobs_dir)
    if job.data["state"] != rj.REVIEW_READY:
        raise rj.Refused(f"job {job_id}: it is {job.data['state']}: only a job with a review package to apply is read")
    sid, stage = rj.last_agent(job)
    review = (stage or {}).get("review") or {}
    if not (isinstance(sid, str) and pr.SID.fullmatch(sid) and review.get("dir")):
        raise rj.Refused(f"job {job_id}: there is no review package")
    rdir = Path(review["dir"])
    try:
        raw = (rdir / "changes.patch").read_bytes()
        prov = json.loads((rdir / "provenance.json").read_text(encoding="utf-8"))
        text = raw.decode("utf-8")
    except (OSError, ValueError) as e:
        raise rj.Refused(f"job {job_id}: the review package cannot be read ({type(e).__name__})")
    sha = hashlib.sha256(raw).hexdigest()
    if review.get("patch_sha256") != sha or (prov.get("patch") or {}).get("sha256") != sha:
        raise rj.Refused(f"job {job_id}: the patch on disk is not the one the review recorded")
    issue = (job.data.get("inputs") or {}).get("issue")
    if not isinstance(issue, str) or not issue.strip():
        raise rj.Refused(f"job {job_id}: the job has no issue text to read the patch against")
    return job, sid, sha, text, issue


def bundle(job_id, jobs_dir):
    job, sid, sha, text, issue = package(job_id, jobs_dir)
    files = sorted(dict.fromkeys(DIFF_FILE.findall(text)))
    touches = ", ".join(files[:FILES_MAX]) + (f" (and {len(files) - FILES_MAX} more)" if len(files) > FILES_MAX else "") if files else "(none found in the patch)"
    return pr.render(issue, touches, "the job is REVIEW_READY: a review package exists; passing examples do not prove the patch is clean", text), sid, sha


def run(job_id, *, cfg, deps, jobs_dir=rj.JOBS, cap_usd=0.20, max_output=64000, first=FIRST, second=SECOND, models=None):
    """Read the patch of the job with the pair; returns a summary dict. `models` is for tests: {name: scripted chat model}."""
    if not (isinstance(cap_usd, (int, float)) and 0 < cap_usd <= 2) or not (isinstance(max_output, int) and 500 <= max_output <= 100000):
        raise rj.Refused("--cap-usd is above 0 and at most 2; --max-output is 500 to 100000")
    text, sid, sha = bundle(job_id, jobs_dir)
    job = rj.open_job(job_id, jobs_dir)
    summary = {"job": job_id, "sha12": sha[:12], "readings": [], "final": None, "billed_usd": 0.0, "stopped": None, "template_sha256": pr.TEMPLATE_SHA256}
    kind0, rec0 = pr.load(job.dir, sid, sha)
    resume = (kind0 in ("one", "concerns") and isinstance(rec0, dict) and rec0["reader"].get("kind") == "argus"
              and rec0["reader"].get("id") == reader_id(first) and "second" not in rec0)      # the first reading stands (ok or concerns): only the second is asked
    if kind0 == "ok" or (kind0 == "concerns" and not resume):
        summary["final"] = kind0
        summary["stopped"] = f"the patch already has a final reading ({kind0}); nothing is read again"
        return summary
    plan = []
    for n, name in enumerate((first, second)):
        if n == 0 and resume:
            continue
        cfg_n, ref = pt._prepare(cfg, name, cap_usd, max_output, None)
        plan.append((name, cfg_n, ref, tr.worst_usd(cfg_n, ref, len(pr.INSTRUCTION) + len(text), max_output)))
    msg = "\n".join([f"patch reading of {job_id} ({sha[:12]}) by {reader_id(first)}, then (only if it says ok) {reader_id(second)}; the readings are notes of the job (patch_read_<sid>.json)",
                     f"worst case per call up to ${max(p[3] for p in plan):.4f}; cap TOTAL for this job's patch readings ${cap_usd:.2f}",
                     f"template {pr.TEMPLATE_SHA256[:12]}; ledger {job.dir / LEDGER}"])
    with rj.live(deps, plan[0][1], [pt.ROLE], msg):
        log = EventLog(job.dir / LEDGER)
        verdicts = []
        for name, cfg_n, ref, worst in plan:
            n = 1 if name == second else 0
            totals = reconcile_ledger(log.read())[1]
            if not totals["usd_complete"]:
                summary["stopped"] = "the ledger is not complete (a call without a price): stopped"
                break
            if totals["usd"] + worst > cap_usd:
                summary["stopped"] = f"cost cap: billed ${totals['usd']:.6f} + worst case ${worst:.6f} > ${cap_usd:.2f}"
                break
            caller = LLMCaller(cfg_n, pt.ROLE, log, model=(models or {}).get(name))
            res = tr.reservation(len(text), max_output, worst)
            try:
                reply = caller.call([SystemMessage(pr.INSTRUCTION), HumanMessage(text)], res,
                                    meta={"node": "patch_reader", "task": f"{job_id}-{sid}", "iteration": n + 1, "step": 0})
            except (LLMCallFailed, ReservationExhausted) as e:
                summary["readings"].append({"reader": reader_id(name), "usable": False, "why": f"call failed: {type(e).__name__}"})
                break
            if is_truncated(reply):
                summary["readings"].append({"reader": reader_id(name), "usable": False, "why": "the reply was cut at the output limit"})
                break
            got = pt.parse(tr.text_of(reply))
            if got is None:
                summary["readings"].append({"reader": reader_id(name), "usable": False, "why": "the reply is not the asked JSON"})
                break
            verdict, note = got
            try:
                pr.record(job_id, sha, verdict, note, "argus", reader_id(name), deps=deps, jobs_dir=jobs_dir, second=(n == 1))
            except rj.Refused as e:                           # the job changed while the model read (a manual note, a new patch): the reading is not written
                summary["readings"].append({"reader": reader_id(name), "usable": False, "why": f"not written: {str(e).split(': ', 1)[-1].split('; nothing')[0]}"})
                break
            summary["readings"].append({"reader": reader_id(name), "usable": True, "verdict": verdict})
            verdicts.append(verdict)                           # a `concerns` of the first reader does not stop the second: both readers' findings are wanted in one note
        summary["billed_usd"] = reconcile_ledger(log.read())[1]["usd"]
    kind, _ = pr.load(job.dir, sid, sha)
    summary["final"] = kind
    return summary
