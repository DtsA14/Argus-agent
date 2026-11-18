"""argus: a code task as one job (router v0, docs/reviews/SPEC_ROUTER_V0.md).

  python scripts/argus.py code --repo ../target --commit HEAD --issue-file issue.txt [--max-usd 1.0] [--exclude docs]
  python scripts/argus.py list                            # every job: its id, state and money (read only)
  python scripts/argus.py status <job>
  python scripts/argus.py approve <job> --sha <first 12 of the draft sha, as status shows it> [--max-usd X]
  python scripts/argus.py reject <job> "why"             # a draft, or a review package that will not be applied
  python scripts/argus.py applied <job> --commit <sha>   # the review package was applied in that commit of the repo
  python scripts/argus.py apply <job> --read-sha <sha>   # apply the patch whose sha status prints: one commit in the repo, then the same record
  python scripts/argus.py redraft <job>
  python scripts/argus.py resume <job>
  python scripts/argus.py retry <job> [--max-usd X] [--not-a-conflict]   # after AGENT_FAILED: the agent again, as a new stage
  python scripts/argus.py abandon <job> "why"            # close a job that will not be continued

Every live stage shows its limits, asks [y/N], then asks for the API key (not shown; never an argument, never written).
Without a terminal (docs/reviews/SPEC_ROUTER_KEY_FILE.md): --key-file PATH reads the key from a 0600 file of yours
outside every repository and jobs/, and --yes (only with --key-file) skips the [y/N] for a run the human approved in
chat; the limits are still printed. Both go after the command:
  python scripts/argus.py approve <job> --sha <sha> --key-file ~/.config/argus/deepseek_key --yes
Applying the review package's patch to the target repository stays with the human. Exit codes: 0 done, 1 the stage
ended without success, 2 refused.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from approve_draft import sandbox_cfg  # noqa: E402  (scripts/ is on sys.path when this file runs)
from acceptance import intake  # noqa: E402
from models.registry import ConfigError  # noqa: E402
from router import job as rj  # noqa: E402
from runner import load_config  # noqa: E402


def _alert(sa, st):
    """The failure notification after a monitor run; it never changes the monitor's verdict or exit code."""
    try:
        sent = sa.after_monitor(st.base)
    except Exception as e:                               # noqa: BLE001
        sent = f"{type(e).__name__}: {e}"
    if sent:
        print(f"alert: {sent}")


def stage_viewer(o, deps):
    """argus stage viewer-deploy|viewer-rollback|viewer-status|viewer-smoke|proxy (SPEC_PWA_VIEWER S)."""
    from router import stage_viewer as sv
    from tools import sandbox as sb
    if o.stage_cmd == "proxy":
        sv.serve()
        return 0
    try:
        if o.stage_cmd == "viewer-smoke":
            results = sv.smoke(sv.Viewer(), sv.PORT)
            for check, ok, detail in results:
                print(f"{'ok  ' if ok else 'FAIL'} {check}: {detail}")
            return 0 if results and all(r[1] for r in results) else 1
        if o.stage_cmd == "viewer-deploy":
            cfg = load_config(o.config)
            cfg["sandbox"] = sandbox_cfg(o.config)
            deps.assume_yes = o.yes
            sv.deploy(o.job, cfg=cfg, deps=deps, jobs_dir=o.jobs_dir)
        elif o.stage_cmd == "viewer-rollback":
            deps.assume_yes = o.yes
            sv.rollback(deps=deps)
    except (rj.Refused, ConfigError, OSError, ValueError, intake.IntakeError, subprocess.TimeoutExpired,
            sb.SandboxUnavailable) as e:
        print(f"refused: {type(e).__name__ + ': ' if not isinstance(e, rj.Refused) else ''}{e}", file=sys.stderr)
        print(sv.status())
        return 2
    text = sv.status()
    print(text)
    return 2 if text.startswith(sv.STATE_PROBLEM) else 0


def _ids(text):
    """--allow-failed-examples: e2,e5 (ids of examples, nothing else)."""
    import re
    ids = [t.strip() for t in str(text).split(",") if t.strip()]
    if not ids or any(not re.fullmatch(r"e[1-9][0-9]?", t) for t in ids):
        raise argparse.ArgumentTypeError("the ids of examples, like e2,e5")
    return tuple(ids)


def main(argv=None, deps=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config")
    ap.add_argument("--jobs-dir", default=str(rj.JOBS))
    ap.add_argument("--queues-dir", default=str(rj.ROOT / "queues"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("code")
    c.add_argument("--repo", required=True)
    c.add_argument("--commit", required=True)
    g = c.add_mutually_exclusive_group(required=True)
    g.add_argument("--issue")
    g.add_argument("--issue-file")
    c.add_argument("--max-usd", type=float)
    c.add_argument("--exclude", action="append", default=[])
    c.add_argument("--environment", help="the sandbox environment of the job's validations (its image is pinned for "
                   "the whole job); without it, the drafter's configured one, nothing pinned")
    c.add_argument("--research", action="store_true", help="start with the research stage r1: read-only tools and ReadDocs "
                   "(granted by this confirmation; needs --environment in web.environments); docs/reviews/SPEC_RESEARCH_STAGE.md")
    c.add_argument("--from-research", metavar="JOB", help="a finished research job (REPORT_READY, checked by e1): its "
                   "SUPPORTED items and their quotes go to the drafter and the agent; docs/reviews/SPEC_FROM_RESEARCH.md")
    c.add_argument("--items", help="with --from-research: the items to take, comma-separated (e.g. S,P2,P5), "
                   "among the SUPPORTED ones")
    sub.add_parser("list")
    sub.add_parser("status").add_argument("job")
    sub.add_parser("resume").add_argument("job")
    d = sub.add_parser("redraft")
    d.add_argument("job")
    d.add_argument("--note", help="a note for the drafter from the reviewer of the previous draft (at most 1000 "
                   "characters; the job is then marked human-steered)")
    a = sub.add_parser("approve")
    a.add_argument("job")
    a.add_argument("--sha", required=True)
    a.add_argument("--max-usd", type=float)
    a.add_argument("--max-iterations", type=int, default=3)
    a.add_argument("--reference-patch")
    a.add_argument("--web", action="store_true", help="grant the agent ReadDocs (documentation pages from the hosts in "
                   "config web.hosts); refused for an environment off web.environments")
    jg = sub.add_parser("judge", help="advice on a finished code job: PASS or BLOCK from another model; the job is not "
                        "changed (docs/reviews/SPEC_JUDGE.md)")
    jg.add_argument("job")
    q = sub.add_parser("research-ok")
    q.add_argument("job")
    q.add_argument("--sha", required=True, help="the handoff sha status shows (at least 12 characters)")
    t = sub.add_parser("retry")
    t.add_argument("job")
    t.add_argument("--max-usd", type=float)
    t.add_argument("--not-a-conflict", action="store_true",
                   help="after BLOCKED/test_conflict: you judge the old tests right; the agent runs again told so, and "
                        "cannot report a conflict in that run")
    ap_ = sub.add_parser("apply", help="apply the review package's patch to the target repository (one commit) and record it (SPEC_ARGUS_APPLY)")
    ap_.add_argument("job")
    ap_.add_argument("--read-sha", required=True, help="the patch's sha256 that status prints, at least 12 characters: you read that patch")
    ap_.add_argument("--note")
    ap_.add_argument("--reader", choices=("claude", "argus"), help="who wrote the patch-read note (a statement, not a proof that the patch was read): recorded as a field of the log entries (SPEC_KARTU_SETUJU 5)")
    ap_.add_argument("--allow-failed-examples", type=_ids, default=(), metavar="ID,ID", help="apply although these examples of the issue failed on the patch: "
                     "name exactly the ids that failed (status lists them); recorded in the job log (SPEC_EXAMPLE_GATE)")
    t3b = sub.add_parser("t3b-run", help="one round of the T3b test of the domain reader with an Argus model (GLM, role code_judge) as the reader, outside the approval card: costs money, has its own cap (SPEC_KARTU_SETUJU 8)")
    t3b.add_argument("root", help="the directory built by scripts/t3b_fixtures.py build")
    t3b.add_argument("--run", type=int, choices=(1, 2), required=True, help="which of the two readings of every set")
    t3b.add_argument("--limit", type=int, help="read at most this many sets (a measuring call first)")
    t3b.add_argument("--cap-usd", type=float, default=0.50, help="the TOTAL cap of this T3b directory (run 1 and run 2 share one ledger): a call starts only if billed so far + its worst case fits")
    t3b.add_argument("--max-output", type=int, default=6000, help="output tokens a call may use (a reasoning model spends them on thinking first)")
    t3b.add_argument("--effort", choices=("low", "medium", "high"), help="the provider's reasoning effort for this run (OpenRouter reasoning.effort, set in a copy of the config; default: the provider's)")
    pt = sub.add_parser("patch-trial", help="a trial of one model as the PATCH reader on eight planted patches (SPEC_KARTU_SETUJU 5), outside the approval card: costs money, own cap, writes nothing to a job")
    pt.add_argument("root", help="the trial directory (created); ledger and readings of all models live here")
    pt.add_argument("--model", required=True, help="a name of router/patch_trial.MODELS")
    pt.add_argument("--run", type=int, choices=(1, 2), required=True)
    pt.add_argument("--cap-usd", type=float, default=0.50, help="the TOTAL cap of the directory (all models share the ledger)")
    pt.add_argument("--max-output", type=int, default=8000)
    pt.add_argument("--effort", choices=("low", "medium", "high"))
    pt.add_argument("--limit", type=int)
    er_ = sub.add_parser("examples-read", help="the domain reader's bundle and note for one item of a PRD (SPEC_KARTU_SETUJU 5 rev 2): a Claude session's statement, not a proof and not a human")
    er_.add_argument("job", help="the PRD job")
    er_.add_argument("--item", required=True, type=int)
    er_.add_argument("--bundle", action="store_true", help="print exactly what the reader sees, then its sha")
    er_.add_argument("--status", action="store_true", help="the note of the item against the bundle as it is now")
    er_.add_argument("--verdict", choices=("ok", "concerns"), help="the note is a statement: nothing proves the reader read the bundle")
    er_.add_argument("--bundle-sha", help="the sha `--bundle` printed")
    er_.add_argument("--reader-id", help="the model or session that read it")
    er_.add_argument("--source", action="append", default=[], help="where a rule comes from: 'permintaan Atha', 'dokumen repo: <file>' or 'hanya tulisan penulis' (repeat)")
    er_.add_argument("--note", help="what you checked and what you found")
    er_.add_argument("--second", action="store_true", help="the second, independent reading (another --reader-id than the first): `ok` needs two")
    pr_ = sub.add_parser("patch-read", help="the note of a patch reader before `apply` (SPEC_KARTU_SETUJU 5): a Claude session's statement, not a proof and not a human")
    pr_.add_argument("job")
    pr_.add_argument("--sha", required=True, help="the sha256 of the patch you read (status prints it), at least 12 characters")
    pr_.add_argument("--verdict", required=True, choices=("ok", "concerns"))
    pr_.add_argument("--note", required=True, help="what you read and what you found")
    pr_.add_argument("--reader", required=True, choices=("claude",))
    pr_.add_argument("--reader-id", help="the model or session that read it (an `ok` needs two readings by two different ids: the second with --second)")
    pr_.add_argument("--second", action="store_true", help="the second reading, by another --reader-id than the first (SPEC_KARTU_SETUJU 13.5)")
    prr = sub.add_parser("patch-read-run", help="the patch reader of an Argus job: Tencent Hy4 Flash, then (only if it says ok) DeepSeek V4.1 Flash 1017, outside a Claude session; costs money, has its own cap")
    prr.add_argument("job")
    prr.add_argument("--cap-usd", type=float, default=0.10, help="the TOTAL cap of this job's patch readings (a call starts only if billed so far + its worst case fits)")
    prr.add_argument("--max-output", type=int, default=12000)
    p = sub.add_parser("applied")
    p.add_argument("job")
    p.add_argument("--commit", required=True, help="the commit of the target repository the patch was applied in")
    p.add_argument("--note")
    p.add_argument("--allow-failed-examples", type=_ids, default=(), metavar="ID,ID", help="as for apply: the ids of the examples that failed on the patch")
    g = sub.add_parser("stage", help="staging (docs/reviews/SPEC_STAGING_V0.md, SPEC_DEP_UPGRADE_V0.md, "
                                     "SPEC_PWA_VIEWER.md): deploy | rollback | status | check | viewer-* | proxy")
    gs = g.add_subparsers(dest="stage_cmd", required=True)
    gd = gs.add_parser("deploy")
    gd.add_argument("job")
    from router.stage import ENVIRONMENT as STAGING_DEFAULT, RUNTIMES as STAGING_RUNTIMES
    gd.add_argument("--runtime", default=STAGING_DEFAULT, choices=sorted(STAGING_RUNTIMES),
                    help="the staging runtime; another than the default needs a passed `stage check` of the commit")
    gc = gs.add_parser("check", help="the job's commit's tests in a sandbox environment (no model, no deploy)")
    gc.add_argument("job")
    gc.add_argument("--env", required=True, choices=sorted(e for e in STAGING_RUNTIMES.values() if e),
                    help="the sandbox environment of a staging runtime")
    gvd = gs.add_parser("viewer-deploy", help="the viewer job's applied commit, built in pwa_node22 and published")
    gvd.add_argument("job")
    grs = gs.add_parser("restart", help="start the live release again on its recorded image when its container is gone")
    for p_ in (gd, gs.add_parser("rollback"), grs, gvd, gs.add_parser("viewer-rollback")):
        p_.add_argument("--yes", action="store_true", help="the deployment was approved in chat (\"go live\")")
    gs.add_parser("viewer-status")
    gs.add_parser("viewer-smoke", help="the smoke test of the live viewer release through the proxy on 127.0.0.1:8710")
    gs.add_parser("proxy", help="the viewer's proxy on 127.0.0.1:8710, forever (systemd --user)")
    gs.add_parser("status")
    for name, text in (("refresh", "a new snapshot of the real jobs' ledgers (allowlisted fields, validated, atomic)"),
                       ("monitor", "refresh, then the smoke test of the live release; recorded; changes no container"),
                       ("report", "the live release's summary and jobs as an escaped HTML page in ~/argus-staging/reports")):
        gs.add_parser(name, help=text)
    isp = sub.add_parser("issue", help="the issue writer: a conversation that writes an issue (SPEC_ISSUE_WRITER)")
    isub = isp.add_subparsers(dest="issue_cmd", required=True)
    for name in ("new", "reply"):
        ip = isub.add_parser(name)
        if name == "new":
            ip.add_argument("--repo", required=True, help="a name of issue_writer.repos in the config")
            ip.add_argument("--job-id", help="the new job's id (the control service picks it to show its page)")
        else:
            ip.add_argument("job")
        im = ip.add_mutually_exclusive_group(required=True)
        im.add_argument("--message")
        im.add_argument("--message-file")
        ip.add_argument("--via", choices=rj.VIA, help="where the message was written (SPEC_CONTROL_UI F4)")
        ip.add_argument("--key-file", action="append",
                        help="read the API key from this 0600 file instead of typing it")
        ip.add_argument("--yes", action="store_true", help="only with --key-file: the run was approved in chat")
    ist = isub.add_parser("start", help="a code job (argus code) from the job's last issue, the one the human saw")
    ist.add_argument("job")
    ist.add_argument("--sha", required=True, help="the issue's sha as status shows it (12+ hex)")
    ist.add_argument("--via", choices=rj.VIA, help="where the start was decided (SPEC_CONTROL_UI F4)")
    ist.add_argument("--key-file", action="append", help="read the API key from this 0600 file instead of typing it")
    ist.add_argument("--yes", action="store_true", help="only with --key-file: the run was approved in chat")
    qp = sub.add_parser("queue", help="issues in order on one repository, each on the commit the one before was applied as (docs/reviews/SPEC_PRD_QUEUE.md)")
    qsub = qp.add_subparsers(dest="queue_cmd", required=True)
    qn = qsub.add_parser("new", help="a queue (PENDING): nothing runs until `go`")
    qn.add_argument("--repo", required=True, help="a name of issue_writer.repos in the config")
    qn.add_argument("--commit", required=True, help="the repository's HEAD now")
    qn.add_argument("--max-usd", type=float, required=True, help="the queue's money; at most $5.00")
    qn.add_argument("--issue-file", action="append", required=True, help="one issue per file, in order (repeat)")
    qg = qsub.add_parser("go", help="approve the list and the money (its sha, as `new` and `status` print it)")
    qg.add_argument("queue")
    qg.add_argument("--sha", required=True)
    qs = qsub.add_parser("step", help="at most one drafter run; otherwise what waits for a human. Never approves or applies")
    qs.add_argument("queue")
    qs.add_argument("--key-file", action="append", help="read the API key from this 0600 file instead of typing it")
    qs.add_argument("--yes", action="store_true", help="only with --key-file: the run was approved in chat")
    qsub.add_parser("status").add_argument("queue")
    qc = qsub.add_parser("close", help="close a stuck queue; no job is touched")
    qc.add_argument("queue")
    qc.add_argument("--note", required=True)
    pp = sub.add_parser("prd", help="a PRD folder (PRD.md, issues.json, issue-<n>.md) checked against the data paths that pass through Argus, then approved once (docs/reviews/SPEC_PRD_STAGE.md)")
    psub = pp.add_subparsers(dest="prd_cmd", required=True)
    psub.add_parser("check", help="read only, no model, no money: BLOCK and WARN findings and the folder's sha").add_argument("dir")
    pa = psub.add_parser("approve", help="the same check on the same bytes, then a PENDING queue (the money is still `queue go`)")
    pa.add_argument("dir")
    pa.add_argument("--sha", required=True, help="the folder's sha as `prd check` prints it (12+ hex)")
    for name in ("new", "reply"):
        pn = psub.add_parser(name, help="the PRD writer: a conversation that writes a PRD folder (docs/reviews/SPEC_PRD_WRITER.md)")
        if name == "new":
            pn.add_argument("--repo", required=True, help="a name of issue_writer.repos in the config")
            pn.add_argument("--job-id", help="the new job's id")
        else:
            pn.add_argument("job")
            pn.add_argument("--rebase", action="store_true", help="freeze the commit again at the repository's HEAD now (the notes are dropped)")
        pm = pn.add_mutually_exclusive_group(required=True)
        pm.add_argument("--message")
        pm.add_argument("--message-file")
        pn.add_argument("--key-file", action="append", help="read the API key from this 0600 file instead of typing it")
        pn.add_argument("--yes", action="store_true", help="only with --key-file: the run was approved in chat")
    cs = sub.add_parser("control", help="the phone's control service (docs/reviews/SPEC_CONTROL_UI.md 4a)")
    cs.add_subparsers(dest="control_cmd", required=True).add_parser(
        "serve", help="reject and abandon from the phone, forever, on 127.0.0.1:8711 only (systemd --user); retired at C4b by `chat serve --port 8711`, code removed at C5")
    ch = sub.add_parser("chat", help="the phone's chat app, read only in C1 (docs/reviews/SPEC_CHAT_APP.md)")
    chs = ch.add_subparsers(dest="chat_cmd", required=True).add_parser(
        "serve", help="the jobs' state and cost as a chat page, forever, on 127.0.0.1:8712 (8711 after C4b) only (systemd --user)")
    chs.add_argument("--port", type=int, choices=(8711, 8712), default=8712,
                     help="8712 while the chat is built; 8711 once it replaced the control service (SPEC_CHAT_APP 13)")
    rs = sub.add_parser("research", help="a deep research job: planner, web workers, synthesis, claim checker (docs/reviews/SPEC_RESEARCH_JOB.md)")
    gq = rs.add_mutually_exclusive_group(required=True)
    gq.add_argument("--question")
    gq.add_argument("--question-file")
    rs.add_argument("--max-usd", type=float)
    rs.add_argument("--profile", help="the models of each stage (research_job.profiles; default research_job.profile)")
    rs.add_argument("--via", choices=rj.VIA, help="where the job was started (SPEC_CHAT_APP 12: the chat's daily cap counts it)")
    rs.add_argument("--job-id", help="the new job's id (the chat picks it to show its page); with --via the exact shape of a harness id, now")
    for name in ("reject", "abandon"):
        r = sub.add_parser(name)
        r.add_argument("job")
        r.add_argument("reason")
        r.add_argument("--sha", help="the draft the human saw (12+ hex): refused when the job's last draft is another")
        r.add_argument("--via", choices=rj.VIA, help="where the decision was made (SPEC_CONTROL_UI F4)")
    for name, p in sub.choices.items():
        if name in ("code", "approve", "redraft", "resume", "retry", "research-ok", "research", "judge", "t3b-run", "patch-trial", "patch-read-run"):   # the live commands
            p.add_argument("--key-file", action="append",
                           help="read the API key from this 0600 file instead of typing it; for a stage that needs "
                                "keys of more than one provider, repeat it as --key-file PROVIDER=PATH")
            p.add_argument("--yes", action="store_true", help="only with --key-file: the run was approved in chat")
    o = ap.parse_args(argv)
    deps = deps or rj.Deps()
    if o.cmd == "control":
        from router import control as rc
        rc.serve(Path(o.jobs_dir), cfg=load_config(o.config))
        return 0
    if o.cmd == "chat":
        from router import chat as rchat
        try:
            cfg = load_config(o.config)
        except (OSError, ValueError) as e:             # the config cannot be read: the chat still serves the jobs, read only
            print(f"argus chat: the config cannot be read ({type(e).__name__}); read only", file=sys.stderr, flush=True)
            cfg = None
        rchat.serve(Path(o.jobs_dir), cfg=cfg, config_path=o.config, load=(lambda: load_config(o.config)), port=o.port,
                    queues_dir=Path(o.queues_dir))
        return 0
    if o.cmd == "stage":
        from router import stage as sg
        from tools import sandbox as sb
        try:
            if o.stage_cmd == "status":
                text = sg.status()
                print(text)
                return 2 if text.startswith(sg.STATE_PROBLEM) else 0
            if o.stage_cmd.startswith("viewer-") or o.stage_cmd == "proxy":   # never a container of argus-ledger
                return stage_viewer(o, deps)
            cfg = load_config(o.config)
            cfg["sandbox"] = sandbox_cfg(o.config)
            if o.stage_cmd in ("refresh", "monitor", "report"):   # no container is started, stopped or replaced
                from router import stage_data as sd
                st = sg.Staging()
                if o.stage_cmd == "refresh":
                    man = sd.refresh(Path(o.jobs_dir), st.data)
                    print(f"refresh: {len(man['jobs'])} jobs, {len(man['excluded'])} excluded, ${man['cost_nano'] / 1e9:.4f}")
                    for e in man["excluded"]:
                        print(f"  excluded {e['job']}: {e['why']}")
                    return 0
                if o.stage_cmd == "monitor":
                    from router import stage_viewer as sv
                    from router import stage_alert as sa
                    try:
                        rec = sd.monitor(st, Path(o.jobs_dir), viewer=sv.Viewer(ledger=st))
                    except Exception as e:               # a crashed run is a failed run, so it can be alerted
                        sd._append(st.base / "monitor.jsonl", {
                            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "ok": False,
                            "why": f"the monitor crashed: {type(e).__name__}"})
                        _alert(sa, st)
                        raise
                    print(json.dumps(rec, sort_keys=True))
                    _alert(sa, st)
                    return {True: 0, None: 0}.get(rec.get("ok"), 1)
                print(f"report: {sd.report(st, sg._get)}")
                return 0
            if o.stage_cmd == "check":                   # the sandbox only: nothing outside it changes
                rec = sg.check(o.job, o.env, cfg=cfg, jobs_dir=o.jobs_dir)
                print(f"stage check {'PASS' if rec['ok'] else 'FAIL'}: commit {rec['commit'][:12]} in {rec['environment']} "
                      f"{rec['image'][:19]}, {rec['tests_run']} tests" + (f"; {rec['why']}" if rec["why"] else ""))
                return 0 if rec["ok"] else 1
            deps.assume_yes = o.yes                      # no key is involved: --yes alone is the approval in chat
            if o.stage_cmd == "deploy":
                sg.deploy(o.job, cfg=cfg, deps=deps, jobs_dir=o.jobs_dir, runtime=o.runtime)
            elif o.stage_cmd == "restart":
                sg.restart(cfg=cfg, deps=deps)
            else:
                sg.rollback(cfg=cfg, deps=deps)
        except (rj.Refused, ConfigError, OSError, ValueError, intake.IntakeError, subprocess.TimeoutExpired,
                sb.SandboxUnavailable) as e:
            print(f"refused: {type(e).__name__ + ': ' if not isinstance(e, rj.Refused) else ''}{e}", file=sys.stderr)
            print(sg.status())
            return 2
        print(sg.status())
        return 0
    if getattr(o, "key_file", None) or getattr(o, "yes", False):
        try:
            deps.key_file, deps.assume_yes = rj.key_files(o.key_file), o.yes
        except rj.Refused as e:
            print(f"refused: {e}", file=sys.stderr)
            return 2
        # o.repo is a path only for `code`; `issue new --repo` names a repository (live() adds its path from the job)
        deps.key_forbidden = (rj.ROOT, Path(o.jobs_dir)) + ((Path(o.repo),) if o.cmd == "code" and o.repo else ())
    try:
        if o.cmd == "list":
            print(rj.list_jobs(jobs_dir=o.jobs_dir))
            return 0
        if o.cmd == "status":
            try:
                cfg = load_config(o.config)
                cfg["sandbox"] = sandbox_cfg(o.config)
            except (ConfigError, OSError):
                cfg = None                    # status still reads the job; the image comparison is left out
            print(rj.status(o.job, jobs_dir=o.jobs_dir, cfg=cfg))
            return 0
        if o.cmd in ("reject", "abandon"):
            fn = rj.reject if o.cmd == "reject" else rj.abandon
            print(rj.status(fn(o.job, o.reason, deps=deps, jobs_dir=o.jobs_dir, sha=o.sha, via=o.via).id,
                            jobs_dir=o.jobs_dir))
            return 0
        if o.cmd == "queue" and o.queue_cmd in ("go", "status", "close"):
            from router import queue as rq
            if o.queue_cmd == "status":
                print(rq.status(o.queue, queues_dir=o.queues_dir, jobs_dir=o.jobs_dir))
                return 0
            q = (rq.go(o.queue, sha=o.sha, deps=deps, queues_dir=o.queues_dir) if o.queue_cmd == "go"
                 else rq.close(o.queue, o.note, deps=deps, queues_dir=o.queues_dir))
            print(rq.status(q["id"], queues_dir=o.queues_dir, jobs_dir=o.jobs_dir))
            return 0
        if o.cmd == "patch-trial":
            from router import patch_trial
            summary = patch_trial.run(o.root, o.model, o.run, cfg=load_config(o.config), deps=deps, cap_usd=o.cap_usd, max_output=o.max_output, effort=o.effort, limit=o.limit)
            print(json.dumps(summary, indent=1))
            print("\n".join(patch_trial.score(o.root, o.model)[0]))
            return 0
        if o.cmd == "t3b-run":
            from router import t3b_run
            summary = t3b_run.run(o.root, o.run, cfg=load_config(o.config), deps=deps, cap_usd=o.cap_usd, max_output=o.max_output, limit=o.limit, effort=o.effort)
            print(json.dumps(summary, indent=1))
            return 0
        if o.cmd == "examples-read":
            from router import examples_read as ers
            modes = [bool(o.bundle), bool(o.status), o.verdict is not None]
            if sum(modes) != 1:
                ap.error("examples-read takes exactly one of --bundle, --status or --verdict (with --bundle-sha, --reader-id, --source and --note)")
            if (o.bundle or o.status) and (o.bundle_sha or o.reader_id or o.source or o.note):
                ap.error("--bundle and --status take no note arguments")
            if o.bundle:
                text, info = ers.bundle(o.jobs_dir, o.job, o.item)
                sys.stdout.write(text)
                print(f"=== end of bundle ===\nbundle_sha256: {info['bundle_sha256']}")
                return 0
            if o.status:
                kind, rec = ers.status(o.jobs_dir, o.job, o.item)
                print(f"examples-read note for {o.job} item {o.item}: {kind}" + (f" by {rec['reader']['kind']} {rec['reader'].get('id') or ''}, sources {', '.join(rec['sources']) or 'none'}: {rec['note']} ({ers.LABEL})" if rec else ""))
                return 0
            if not (o.bundle_sha and o.reader_id and o.note):
                ap.error("a note needs --bundle-sha, --reader-id and --note")
            rec = ers.record(o.job, o.item, o.verdict, o.bundle_sha, o.reader_id, o.source, o.note, deps=deps, jobs_dir=o.jobs_dir, second=o.second)
            print(f"examples-read note for {o.job} item {o.item}: {rec['verdict']} by claude: {ers.LABEL}; the note says who wrote it and what bundle it saw, not that the bundle was read")
            return 0
        if o.cmd == "patch-read-run":
            from router import patch_read_run
            summary = patch_read_run.run(o.job, cfg=load_config(o.config), deps=deps, jobs_dir=o.jobs_dir, cap_usd=o.cap_usd, max_output=o.max_output)
            print(json.dumps(summary, indent=1))
            return 0
        if o.cmd == "patch-read":
            from router import patch_read as prd_
            rec = prd_.record(o.job, o.sha, o.verdict, o.note, o.reader, o.reader_id, deps=deps, jobs_dir=o.jobs_dir, second=o.second)
            print(f"patch-read note for {o.job} {rec['sid']} {rec['patch_sha256'][:12]}: {rec['verdict']} by {rec['reader']['kind']}: {prd_.LABEL}")
            return 0
        if o.cmd == "apply":
            from router import apply as ra
            from router import examples_read as ers_
            try:                                # say what the domain reader's note means for this apply, also when it is not asked (a wrong --queues-dir shows here)
                pre = ers_.chain(rj.open_job(o.job, o.jobs_dir), o.jobs_dir, o.queues_dir)
                print("domain reader's note: " + (f"{pre['kind']}" if pre["applicable"] else f"not asked ({pre['why']}; queues directory {o.queues_dir})"))
            except Exception as e:              # a message only: the gate itself is in `apply`
                print(f"domain reader's note: could not be looked at ({type(e).__name__})")
            done = ra.apply(o.job, o.read_sha, deps=deps, jobs_dir=o.jobs_dir, note=o.note, allow_failed_examples=o.allow_failed_examples,
                            reader=o.reader, queues_dir=o.queues_dir)
            print(rj.status(done.id, jobs_dir=o.jobs_dir))
            e = done.data["log"][-1]
            print(f"applied on branch {e.get('branch')} (the commit above; was {str(e.get('head_before'))[:12]}); not pushed, not deployed.\n"
                  f"next: `argus stage deploy {done.id}` needs its PLAN.md and your go live.")
            return 0
        if o.cmd == "applied":
            print(rj.status(rj.applied(o.job, o.commit, deps=deps, jobs_dir=o.jobs_dir, note=o.note,
                                      allow_failed_examples=o.allow_failed_examples).id,
                            jobs_dir=o.jobs_dir))
            return 0
        cfg = load_config(o.config)
        cfg["sandbox"] = sandbox_cfg(o.config)
        if o.cmd == "code":
            issue = o.issue if o.issue is not None else Path(o.issue_file).read_text(encoding="utf-8")
            job = rj.start_code(repo=o.repo, commit=o.commit, issue=issue, cfg=cfg, deps=deps, exclude=o.exclude,
                                max_usd=o.max_usd, jobs_dir=o.jobs_dir, environment=o.environment, research=o.research,
                                from_research=o.from_research,
                                research_items=None if o.items is None else [i.strip() for i in o.items.split(",")
                                                                             if i.strip()])
        elif o.cmd == "issue":
            from router import issue as ri
            if o.issue_cmd == "start":
                job, code = ri.start(o.job, sha=o.sha, cfg=cfg, deps=deps, jobs_dir=o.jobs_dir, via=o.via)
                print(rj.status(code.id, jobs_dir=o.jobs_dir, cfg=cfg))
                return 0 if code.data["state"] == rj.AWAITING_APPROVAL else 1
            message = o.message if o.message is not None else Path(o.message_file).read_text(encoding="utf-8")
            if o.issue_cmd == "new":
                job = ri.new(repo=o.repo, message=message, cfg=cfg, deps=deps, jobs_dir=o.jobs_dir, via=o.via,
                             job_id=o.job_id)
            else:
                job = ri.reply(o.job, message, cfg=cfg, deps=deps, jobs_dir=o.jobs_dir, via=o.via)
            print(rj.status(job.id, jobs_dir=o.jobs_dir, cfg=cfg))
            return 0 if job.data["state"] == ri.AWAITING_HUMAN else 1
        elif o.cmd == "prd":
            from router import prd as rp
            if o.prd_cmd in ("new", "reply"):
                from router import prd_job as pj
                message = o.message if o.message is not None else Path(o.message_file).read_text(encoding="utf-8")
                if o.prd_cmd == "new":
                    job = pj.new(repo=o.repo, message=message, cfg=cfg, deps=deps, jobs_dir=o.jobs_dir,
                                 queues_dir=o.queues_dir, job_id=o.job_id)
                else:
                    job = pj.reply(o.job, message, cfg=cfg, deps=deps, jobs_dir=o.jobs_dir, queues_dir=o.queues_dir,
                                   rebase=o.rebase)
                print(rj.status(job.id, jobs_dir=o.jobs_dir, cfg=cfg))
                return 0 if job.data["state"] == pj.AWAITING_HUMAN else 1
            if o.prd_cmd == "check":
                text, ok = rp.report(o.dir, cfg=cfg, queues_dir=o.queues_dir, jobs_dir=o.jobs_dir)
                print(text)
                return 0 if ok else 1
            if o.prd_cmd != "approve":
                raise AssertionError(o.prd_cmd)
            from router import queue as rq
            q = rp.approve(o.dir, o.sha, cfg=cfg, deps=deps, queues_dir=o.queues_dir, jobs_dir=o.jobs_dir)
            print(f"queue {q['id']} PENDING: {len(q['items'])} issues on {q['name']}, up to ${q['max_usd']:.2f}, from the PRD {q['prd']['sha'][:12]}\n"
                  f"approve the list and the money: argus queue go {q['id']} --sha {rq.list_sha(q)[:12]}")
            return 0
        elif o.cmd == "queue":
            from router import queue as rq
            if o.queue_cmd == "new":
                q = rq.new(repo=o.repo, commit=o.commit, max_usd=o.max_usd, cfg=cfg, deps=deps, queues_dir=o.queues_dir,
                           jobs_dir=o.jobs_dir, issues=[Path(f).read_text(encoding="utf-8") for f in o.issue_file])
                print(f"queue {q['id']}: {len(q['items'])} issues on {q['name']} at {q['base_commit'][:12]}, up to ${q['max_usd']:.2f}\n"
                      f"list sha {rq.list_sha(q)}\napprove the list and the money: argus queue go {q['id']} --sha {rq.list_sha(q)[:12]}")
            else:
                text = rq.step(o.queue, cfg=cfg, deps=deps, queues_dir=o.queues_dir, jobs_dir=o.jobs_dir)
                print(text)
                return 1 if " STOPPED " in text.splitlines()[0] else 0      # a /loop can tell a stopped queue from a waiting one
            return 0
        elif o.cmd == "research":
            from router import research as rr
            question = o.question if o.question is not None else Path(o.question_file).read_text(encoding="utf-8")
            job = rr.start(question=question, cfg=cfg, deps=deps, max_usd=o.max_usd, jobs_dir=o.jobs_dir,
                           profile=o.profile, via=o.via, job_id=o.job_id)
            print(rj.status(job.id, jobs_dir=o.jobs_dir, cfg=cfg))
            return 0 if job.data["state"] == rr.REPORT_READY else 1
        elif o.cmd == "judge":
            from codetask.judge import JUDGED
            job, r = rj.judge(o.job, cfg=cfg, deps=deps, jobs_dir=o.jobs_dir)
            print(rj.status(job.id, jobs_dir=o.jobs_dir, cfg=cfg))
            return 0 if r["status"] == JUDGED else 1
        elif o.cmd == "research-ok":
            job, _ = rj.research_ok(o.job, sha=o.sha, cfg=cfg, deps=deps, jobs_dir=o.jobs_dir)
        elif o.cmd == "approve":
            job, _ = rj.approve(o.job, sha=o.sha, cfg=cfg, deps=deps, sandbox_cfg=cfg["sandbox"], max_usd=o.max_usd,
                                max_iterations=o.max_iterations, reference_patch=o.reference_patch, jobs_dir=o.jobs_dir,
                                web=o.web)
        elif o.cmd == "retry":
            job, _ = rj.retry(o.job, cfg=cfg, deps=deps, sandbox_cfg=cfg["sandbox"], max_usd=o.max_usd,
                              jobs_dir=o.jobs_dir, not_a_conflict=o.not_a_conflict)
        elif o.cmd == "redraft":
            job, _ = rj.redraft(o.job, cfg=cfg, deps=deps, jobs_dir=o.jobs_dir, note=o.note)
        else:
            job, r = rj.resume(o.job, cfg=cfg, deps=deps, sandbox_cfg=cfg["sandbox"], jobs_dir=o.jobs_dir)
            if isinstance(r, dict) and r.get("kind") == "judge":        # a judge stage continued (SPEC_JUDGE J5)
                from codetask.judge import JUDGED
                print(rj.status(job.id, jobs_dir=o.jobs_dir, cfg=cfg))
                return 0 if r["status"] == JUDGED else 1
    except (rj.Refused, ConfigError, OSError) as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        job = getattr(o, "job", None)
        print("\ninterrupted. " + (f"Continue it with `argus resume {job}`; " if job else "")
              + "`argus status <job>` shows where it stopped. Do not start a new job for the same task.", file=sys.stderr)
        return 130
    print(rj.status(job.id, jobs_dir=o.jobs_dir, cfg=cfg))
    from router.research import REPORT_READY              # a resumed research job
    return 0 if job.data["state"] in (rj.AWAITING_APPROVAL, rj.REVIEW_READY, rj.AWAITING_RESEARCH_REVIEW,
                                      REPORT_READY) else 1


if __name__ == "__main__":
    from harness import redact as _redact
    _redact.install()                     # no registered key value reaches the terminal, tracebacks of chained exceptions included
    sys.exit(main())
