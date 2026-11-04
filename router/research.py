"""A research job (docs/reviews/SPEC_RESEARCH_JOB.md §2): `argus research "<question>"`, kind "research".

  NEW -> PLANNING (p1) -> RESEARCHING (w1..wN, in order) -> SYNTHESIZING (s1) -> CHECKING (e1) -> REPORT_READY
                       \\-> PLAN_FAILED                 \\-> RESEARCH_INCONCLUSIVE \\-> SYNTHESIS_FAILED
                                                          (no sub-question answered)
  BLOCKED when a stage cannot be funded or the provider fails; every state -> ABANDONED.

One "go live" per job (Atha 2026-11-03): the [y/N] before the job is created shows the question, the caps, the model,
the web provider and its prices, and that queries and URLs go to DeepSeek; then every stage runs without another
decision. A resume continues the stage a crash interrupted, with the cap that stage started with, and the stages after
it. Each stage runs on its configured cap, recorded when it starts; a stage whose cap is more than what the job's ledgers
leave is not started (BLOCKED), and the findings paid for until then are still written. A worker whose provider fails
also blocks the job (BLOCKED), after writing the findings so far. The plan is written once, when p1 passes, and never changes.
A job is started only when its cap funds every stage at its configured cap (the planner, the most workers a plan may
have, the synthesis and the checker), so a job that runs within its caps is never left without a report for money.
REPORT.md is rendered by the harness when s1 passes (unchecked) and again when e1 ends; e1 only flags (v0): whatever it
says, the job ends REPORT_READY, unless its provider fails or it cannot be funded (BLOCKED, the unchecked REPORT.md kept).
"""
import json
import math
import os
from pathlib import Path

from codetask.drafter import _write

from research import report as rp

from . import job as rj

PLANNING, PLAN_FAILED, RESEARCHING = "PLANNING", "PLAN_FAILED", "RESEARCHING"
INCONCLUSIVE, SYNTHESIZING, SYNTHESIS_FAILED = "RESEARCH_INCONCLUSIVE", "SYNTHESIZING", "SYNTHESIS_FAILED"
CHECKING, REPORT_READY = "CHECKING", "REPORT_READY"
NEW, BLOCKED, ABANDONED = rj.NEW, rj.BLOCKED, rj.ABANDONED
RUNNING = (PLANNING, RESEARCHING, SYNTHESIZING, CHECKING)
LEGAL = {(NEW, PLANNING), (NEW, BLOCKED), (PLANNING, RESEARCHING), (PLANNING, PLAN_FAILED), (PLANNING, BLOCKED),
         (RESEARCHING, SYNTHESIZING), (RESEARCHING, INCONCLUSIVE), (RESEARCHING, BLOCKED),
         (SYNTHESIZING, CHECKING), (SYNTHESIZING, SYNTHESIS_FAILED), (SYNTHESIZING, BLOCKED),
         (CHECKING, REPORT_READY), (CHECKING, BLOCKED)} | \
        {(s, ABANDONED) for s in (NEW, *RUNNING, BLOCKED, PLAN_FAILED, INCONCLUSIVE, SYNTHESIS_FAILED, REPORT_READY)}


STAGE_KINDS = ("planner", "worker", "synthesis", "checker")


def _settings(cfg):
    rcfg = cfg["research_job"]
    wr = cfg.get("web_research") or {}
    return rcfg, wr


def stage_roles(cfg, profile=None):
    """{stage kind: role} of a profile (research_job.profiles; research_job.profile by default). Without profiles every
    stage runs on research_job.role."""
    rcfg = cfg["research_job"]
    profiles = rcfg.get("profiles") or {}
    name = profile or rcfg.get("profile")
    if name is None:
        return {k: rcfg["role"] for k in STAGE_KINDS}
    if name not in profiles:
        raise rj.Refused(f"unknown research profile {name!r}; profiles: {sorted(profiles)}; no job was created")
    roles = profiles[name]
    missing = [k for k in STAGE_KINDS if not (roles or {}).get(k)]
    if missing or any(roles[k] not in cfg.get("roles", {}) for k in STAGE_KINDS):
        raise rj.Refused(f"research profile {name!r} must name an existing role for each of {list(STAGE_KINDS)}; "
                         "no job was created")
    return {k: roles[k] for k in STAGE_KINDS}


def _cfg(job, cfg, cap):
    """A stage's config: the router's overrides, the stage cap, and the job's stage roles (fixed when it was created)."""
    out = rj.stage_config(cfg, cap)
    out["research_job"]["stage_roles"] = dict(job.data["stage_roles"])
    return out


def _web_provider(cfg):
    return (cfg.get("web_research") or {}).get("provider", "deepseek")


def _screen(job, cfg, title):
    """The confirmation screen, from the stage config (cfg: router overrides applied) so it shows what will be called."""
    rcfg, wr = _settings(cfg)
    prices = wr.get("price_usd_per_request") or {}
    plan = job.data.get("plan")
    workers = len(plan["sub_questions"]) if plan else rcfg["planner"]["max_sub_questions"]
    roles = job.data["stage_roles"]
    models = {k: cfg["roles"][r]["model"] for k, r in roles.items()}
    fallbacks = {k: cfg["roles"][r].get("fallback_models") or [] for k, r in roles.items()}
    free = sorted({m for k in models for m in [models[k], *fallbacks[k]] if _is_free(cfg, m)})
    return rj._limits_text(job, title, [
        "question: " + job.data["inputs"]["question"][:300] + ("..." if len(job.data["inputs"]["question"]) > 300 else ""),
        f"profile {job.data['profile']}: " + ", ".join(f"{k} {models[k]}" for k in STAGE_KINDS),
        *([("free fallbacks when rate limited: " + "; ".join(f"{k} " + " -> ".join([models[k], *fallbacks[k]]) for k in STAGE_KINDS
                                                              if fallbacks[k]))] if any(fallbacks.values()) else []),
        f"caps: planner ${rcfg['planner']['cap_usd']:.2f}, {'' if plan else 'up to '}{workers} worker(s) at "
        f"${rcfg['worker']['cap_usd']:.2f} each, synthesis ${rcfg['synthesis']['cap_usd']:.2f}, claim checker "
        f"${rcfg['checker']['cap_usd']:.2f} (it only flags)",
        f"web: {_web_provider(cfg)} Search ${prices.get('search')} and Fetch ${prices.get('fetch')} per "
        f"request, paid from each worker's cap; at most {rcfg['worker']['max_searches']} searches and "
        f"{rcfg['worker']['max_fetches']} fetches per worker",
        f"data sent out: the question, the search queries and the URLs go to {_web_provider(cfg)}, and the prompts to "
        "each stage's model provider; do not put secrets in the question",
        *([f"free models ({', '.join(free)}): their providers may keep the prompts or train on them"] if free else []),
        "tools: WebSearch, WebFetch, Submit; nothing is written outside the job, nothing is sent anywhere else",
        "one confirmation covers every stage of this job (planner, workers, synthesis, claim checker)"])


def _is_free(cfg, model):
    from models import gateway
    from models.registry import ModelRef
    ref = ModelRef.parse(model)
    return gateway.is_gateway(cfg, ref) and gateway.entry(cfg, ref)["free"]


def _preflight(cfg, roles, cap):
    """What every stage needs, checked before the confirmation so no stage is paid for first: both web request kinds
    have a price, the web provider is configured (its key is taken with the models' keys), and each stage's model is
    priced and allowed for its role (a free model only for a listed role without repository tools), and its limits hold
    for that model (research.stages.settings). Checked on the stage config (router overrides applied), as it will run;
    also before a resume, against the roles the job started with."""
    from harness.llm import check_priced
    from models import gateway
    from models.registry import ConfigError, ModelRef
    from research.stages import settings
    _, wr = _settings(cfg)
    if _web_provider(cfg) not in (cfg.get("providers") or {}):
        raise rj.Refused(f"web_research.provider {_web_provider(cfg)!r} is not a configured provider; no job was created")
    prices = wr.get("price_usd_per_request") or {}
    missing = [k for k in ("search", "fetch") if prices.get(k) is None]
    if missing:
        raise rj.Refused(f"web_research.price_usd_per_request has no {', '.join(missing)}; no job was created")
    scfg = rj.stage_config(cfg, cap)
    scfg["research_job"]["stage_roles"] = dict(roles)
    for kind, role in roles.items():
        if role not in scfg.get("roles", {}):
            raise rj.Refused(f"research {kind}: role {role!r} is not in the config; nothing was started")
        try:
            for model in gateway.fallback_chain(scfg, role):       # the role's model, then its free fallbacks
                ref = ModelRef.parse(model)
                check_priced(scfg, ref, f"research {kind} (role {role!r})")
                gateway.check_use(scfg, role, ref)
                mcfg = {**scfg, "roles": {**scfg["roles"], role: {**scfg["roles"][role], "model": model}}}
                settings(mcfg, kind)
        except (ConfigError, KeyError, ValueError) as e:
            raise rj.Refused(f"research {kind} (role {role!r}): {e}; nothing was started") from e


def _need(rcfg):
    return (float(rcfg["planner"]["cap_usd"]) + int(rcfg["planner"]["max_sub_questions"]) * float(rcfg["worker"]["cap_usd"])
            + float(rcfg["synthesis"]["cap_usd"]) + float(rcfg["checker"]["cap_usd"]))


def start(*, question, cfg, deps, max_usd=None, jobs_dir=rj.JOBS, job_id=None, profile=None):
    """A new research job, confirmed once, then every stage. Returns the job."""
    from research.stages import QUESTION_MAX, QUESTION_MIN
    if not isinstance(question, str) or not QUESTION_MIN <= len(question.strip()) <= QUESTION_MAX:
        raise rj.Refused(f"the question must have {QUESTION_MIN} to {QUESTION_MAX} characters; no job was created")
    rcfg, wr = _settings(cfg)
    roles = stage_roles(cfg, profile)
    cap = float(max_usd if max_usd is not None else rcfg.get("max_usd", 1.0))
    need = _need(rcfg)
    if not (math.isfinite(cap) and cap + 1e-9 >= need):
        raise rj.Refused(f"the job cap must be a number of at least ${need:.2f} (the planner, "
                         f"{rcfg['planner']['max_sub_questions']} workers, the synthesis and the checker at their caps); "
                         "no job was created")
    _preflight(cfg, roles, cap)
    job_id = job_id or rj.new_job_id()
    if not rj.JOB_ID.match(job_id):
        raise rj.Refused(f"{job_id!r} is not a job id")
    job = rj.Job(Path(jobs_dir) / job_id)
    if job.file.exists():
        raise rj.Refused(f"job {job_id} already exists")
    with job.lock():
        job.data = {"job": job_id, "kind": "research", "state": NEW, "created_at": deps.clock(), "max_usd": cap,
                    "inputs": {"question": rj.clean(question.strip())}, "stages": {}, "plan": None, "log": [],
                    "profile": profile or rcfg.get("profile") or "default", "stage_roles": roles}
        job.note(deps, "created", by=os.environ.get("USER"))
        try:
            with rj.live(deps, rj.stage_config(cfg, cap), sorted(set(roles.values())),
                         _screen(job, rj.stage_config(cfg, cap), "research job"),
                         job=job, providers=[_web_provider(cfg)]):
                _run(job, cfg, deps)
        except rj.Refused:
            if job.data["state"] == NEW and not job.data["stages"]:
                job.move(ABANDONED, deps, reason="not started: not confirmed or no key")
            raise
    return job


def resume(job, cfg, deps):
    """Continue a research job whose stage was interrupted (the caller holds the job's lock)."""
    if job.data["state"] not in RUNNING:
        raise rj.Refused(f"job {job.id} is {job.data['state']}: nothing to resume")
    job.data.setdefault("stage_roles", {k: cfg["research_job"]["role"] for k in STAGE_KINDS})   # a job from before
    job.data.setdefault("profile", "default")
    _preflight(cfg, job.data["stage_roles"], job.data["max_usd"])
    scfg = rj.stage_config(cfg, job.data["max_usd"])
    with rj.live(deps, scfg, sorted(set(job.data["stage_roles"].values())),
                 _screen(job, scfg, "research job (resume)"), job=job, providers=[_web_provider(cfg)]):
        _run(job, cfg, deps)
    return job


def _cap(job, cfg, deps, which, sid):
    """The stage's cap: the one it started with, or its configured cap when what is left of the job can fund it (None
    and BLOCKED when it cannot)."""
    st = job.data["stages"].get(sid)
    if st is not None:
        return st["cap_usd"]
    want = float(cfg["research_job"][which]["cap_usd"])
    left = rj.left_usd(job)
    if left + 1e-12 < want:
        job.move(BLOCKED, deps, reason=f"budget: ${left:.4f} left for {sid}, its cap is ${want:.2f}")
        return None
    return round(want, 6)


def _start_stage(job, deps, sid, kind, cap):
    if sid not in job.data["stages"]:
        job.data["stages"][sid] = {"kind": kind, "run_id": f"{job.id}-{sid}", "cap_usd": cap, "started_at": deps.clock()}
        job.note(deps, "stage_started", stage=sid)
    run_id = job.data["stages"][sid]["run_id"]
    return run_id, (job.runs / run_id / "checkpoints.sqlite").exists()


def _end_stage(job, deps, sid, r):
    job.data["stages"][sid].update(ended_at=deps.clock(), status=r.get("status"), usd=r.get("usd_billed"))
    job.save()
    deps.echo(f"{sid} finished: {r.get('status')} (${r.get('usd_billed', 0):.4f})")


def _run(job, cfg, deps):
    from research.stages import PLANNED, run_planner
    rcfg = cfg["research_job"]
    question = job.data["inputs"]["question"]
    if job.data["state"] == NEW:
        job.move(PLANNING, deps, stage="p1")
    if job.data["state"] == PLANNING:
        cap = _cap(job, cfg, deps, "planner", "p1")
        if cap is None:
            raise rj.Refused(f"job {job.id}: not enough of the job cap left for the planner (BLOCKED)")
        run_id, again = _start_stage(job, deps, "p1", "plan", cap)
        deps.echo(rj.running(job, "planner", run_id))
        r = run_planner(run_id=run_id, runs_dir=job.runs, cfg=_cfg(job, cfg, cap), question=question, max_usd=cap,
                        resume=again, models=deps.models)
        _end_stage(job, deps, "p1", r)
        if r.get("status") != PLANNED:
            job.move(BLOCKED if r.get("status") == "BLOCKED" else PLAN_FAILED, deps, stage="p1",
                     reason=r.get("stop_reason"))
            return
        job.data["plan"] = r["plan"]
        _write(job.dir / "plan.json", json.dumps(r["plan"], indent=2, ensure_ascii=False) + "\n")
        job.move(RESEARCHING, deps, stage="p1", sub_questions=len(r["plan"]["sub_questions"]))
    if job.data["state"] == RESEARCHING:
        _research(job, cfg, deps, question)
    if job.data["state"] == SYNTHESIZING:
        cap = _cap(job, cfg, deps, "synthesis", "s1")
        if cap is None:
            raise rj.Refused(f"job {job.id}: not enough of the job cap left for the synthesis (BLOCKED)")
        run_id, again = _start_stage(job, deps, "s1", "report", cap)
        deps.echo(rj.running(job, "synthesis s1", run_id))
        r = rp.run_synthesis(run_id=run_id, runs_dir=job.runs, cfg=_cfg(job, cfg, cap), findings=_collect(job),
                             max_usd=cap, resume=again, models=deps.models)
        _end_stage(job, deps, "s1", r)
        if r.get("status") != rp.REPORTED:
            job.move(BLOCKED if r.get("status") == BLOCKED else SYNTHESIS_FAILED, deps, stage="s1",
                     reason=r.get("stop_reason"))
            return
        _write(job.dir / "report.json", json.dumps(r["report"], indent=2, ensure_ascii=False) + "\n")
        _write_report(job)
        job.move(CHECKING, deps, stage="s1")
    if job.data["state"] == CHECKING:
        cap = _cap(job, cfg, deps, "checker", "e1")
        if cap is None:
            raise rj.Refused(f"job {job.id}: not enough of the job cap left for the claim checker (BLOCKED); "
                             f"the unchecked report is {job.dir / 'REPORT.md'}")
        run_id, again = _start_stage(job, deps, "e1", "check", cap)
        deps.echo(rj.running(job, "claim checker e1", run_id))
        report = json.loads((job.dir / "report.json").read_text(encoding="utf-8"))
        r = rp.run_check(run_id=run_id, runs_dir=job.runs, cfg=_cfg(job, cfg, cap), report=report,
                         findings=_collect(job), max_usd=cap, resume=again, models=deps.models)
        _end_stage(job, deps, "e1", r)
        check = {k: r.get(k) for k in ("status", "stop_reason", "verdicts")}
        _write(job.dir / "check.json", json.dumps(check, indent=2, ensure_ascii=False) + "\n")
        job.data["stages"]["e1"]["counts"] = rp.counts(check)
        job.save()
        _write_report(job)
        if r.get("status") == BLOCKED:                     # the provider failed: the report stays unchecked
            job.move(BLOCKED, deps, stage="e1", reason=r.get("stop_reason"))
            return
        job.move(REPORT_READY, deps, stage="e1", check=r.get("status"), **rp.counts(check))


def _research(job, cfg, deps, question):
    """The workers, in plan order, then findings.json and the next state (SYNTHESIZING, INCONCLUSIVE or BLOCKED)."""
    from research.stages import ANSWERED, run_worker
    paid = getattr(deps, "paid", None)
    for n, sub in enumerate(job.data["plan"]["sub_questions"], 1):
        sid = f"w{n}"
        st = job.data["stages"].get(sid)
        if st is not None and st.get("ended_at"):
            continue
        cap = _cap(job, cfg, deps, "worker", sid)
        if cap is None:
            _write_findings(job)
            raise rj.Refused(f"job {job.id}: not enough of the job cap left for {sid} (BLOCKED)")
        run_id, again = _start_stage(job, deps, sid, "research_worker", cap)
        deps.echo(rj.running(job, f"worker {sid} ({sub['id']})", run_id))
        r = run_worker(run_id=run_id, runs_dir=job.runs, cfg=_cfg(job, cfg, cap), question=question, sub=sub,
                       max_usd=cap, resume=again, models=deps.models, **({"paid": paid} if paid else {}))
        _end_stage(job, deps, sid, r)
        if r.get("findings"):
            job.data["stages"][sid]["verdict"] = r["findings"]["verdict"]
            job.data["stages"][sid]["findings"] = len(r["findings"]["findings"])
            job.save()
        if r.get("status") == "BLOCKED":                   # the provider failed: not a missing answer
            _write_findings(job)
            job.move(BLOCKED, deps, stage=sid, reason=r.get("stop_reason"))
            return
    findings = _write_findings(job)
    answered = any(f["verdict"] == ANSWERED for f in findings["workers"])
    n = sum(len(f["findings"]) for f in findings["workers"])
    job.move(SYNTHESIZING if answered else INCONCLUSIVE, deps, findings=n)


def _write_report(job):
    """REPORT.md from report.json, the findings and check.json (when e1 has ended), rendered by the harness."""
    report = json.loads((job.dir / "report.json").read_text(encoding="utf-8"))
    check_file = job.dir / "check.json"
    check = json.loads(check_file.read_text(encoding="utf-8")) if check_file.exists() else None
    _write(job.dir / "REPORT.md", rp.render(_collect(job), report, check, job_id=job.id))


def _write_findings(job):
    findings = _collect(job)
    _write(job.dir / "findings.json", json.dumps(findings, indent=2, ensure_ascii=False) + "\n")
    return findings


def _collect(job):
    """The plan and every worker's gated findings (ids W<n>.F<m>), from the stage runs' result.json files."""
    out = {"question": job.data["inputs"]["question"], "plan": job.data["plan"], "workers": []}
    for n, sub in enumerate(job.data["plan"]["sub_questions"], 1):
        sid = f"w{n}"
        st = job.data["stages"].get(sid) or {}
        if not st.get("ended_at"):
            continue                                       # not run (or not finished) yet: nothing to collect
        try:
            r = json.loads((job.runs / st["run_id"] / "result.json").read_text(encoding="utf-8"))
        except (OSError, ValueError, KeyError):
            r = {}
        f = r.get("findings") or {"verdict": r.get("status") or "NOT_RUN", "findings": [], "uncertainties": []}
        out["workers"].append({"stage": sid, "sub_question": sub, "status": r.get("status"), "verdict": f["verdict"],
                               "findings": [{**x, "id": f"W{n}.{x['id']}"} for x in f["findings"]],
                               "uncertainties": f["uncertainties"],
                               **({"dropped": f["dropped"]} if f.get("dropped") else {})})
    return out


def status_lines(job):
    d = job.data
    out = [f"job {job.id}: {d['state']} (research)", "question: " + d["inputs"]["question"][:200],
           f"money: cap ${d['max_usd']:.2f}, spent ${rj.spent_nano(job) / 1e9:.4f}"]
    if d.get("stage_roles"):
        out.append(f"profile {d.get('profile')}: " + ", ".join(f"{k} {r}" for k, r in d["stage_roles"].items()))
    for sid, s in d["stages"].items():
        out.append(f"  {sid} {s['kind']}: {s.get('status', 'running')} cap ${s['cap_usd']:.4f}"
                   + (f" spent ${s['usd']:.4f}" if s.get("usd") is not None else "")
                   + (f"; {s['verdict']}, {s['findings']} finding(s)" if s.get("verdict") else ""))
    if d.get("plan"):
        out += [f"plan ({job.dir / 'plan.json'}):"] + [f"  {q['id']} {q['question'][:150]}" for q in d["plan"]["sub_questions"]]
    if (job.dir / "findings.json").exists():
        out.append(f"findings: {job.dir / 'findings.json'}")
    if (job.dir / "REPORT.md").exists():
        c = (d["stages"].get("e1") or {}).get("counts")
        out.append(f"report: {job.dir / 'REPORT.md'}" + (
            f" (e1 flags: {c[rp.SUPPORTED]} supported, {c[rp.PARTIAL]} partial, {c[rp.UNSUPPORTED]} unsupported)"
            if c and d["stages"]["e1"].get("status") == rp.CHECKED else " (not checked by e1)"))
    if d["state"] in RUNNING:
        out.append(f"next (if no stage is running): argus resume {job.id}")
    if d["state"] in (BLOCKED, PLAN_FAILED, ABANDONED, INCONCLUSIVE, SYNTHESIS_FAILED):
        why = rj._why(job)
        out.append(f"why: {why.get('reason') or 'not recorded'}")
    return out
