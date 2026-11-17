"""SPEC_EXAMPLE_GATE PR 2: the examples of an issue as a gate on a code job. Intake (a wrong example BLOCKS the job before any
drafter money), the audit after the agent (fail closed, bound to the patch's sha256, run again by `argus resume`), and
`argus apply` / `argus applied` (refuse a failed, missing, pending or stale result unless the human names exactly the failed ids).
The runner is a local process on a copy of the tree, not the sandbox (tests/test_examples_sandbox.py has the container)."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_router as tr  # noqa: E402
from test_examples import make_tree  # noqa: E402
from codetask import examples as ex  # noqa: E402
from router import apply as ra  # noqa: E402
from router import example_gate as eg  # noqa: E402
from router import job as rj  # noqa: E402
from router import stage_data  # noqa: E402
from tools.sandbox import SandboxUnavailable  # noqa: E402

td = tr.td
pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="posix")

SAME = {"id": "e1", "tier": "same", "says": "Two prices and a discount of 1 give 4", "setup": "from src.shop import total",
        "run": "total([2, 3], 1)", "expect": 4}
AFTER = {"id": "e2", "tier": "after", "says": "A discount larger than the sum floors at 0", "setup": "from src.shop import total",
         "run": "total([1], 5)", "expect": 0}
WRONG_AFTER = {**AFTER, "expect": 99}


def block(*examples):
    return "```argus-examples\n" + json.dumps(list(examples)) + "\n```\n"


def issue_with(*examples):
    return td.ISSUE + "\n\n" + block(*examples)


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    h.mkdir()
    (h / ".gitconfig").write_text("[user]\n\tname = Global Person\n\temail = global@example.org\n")
    monkeypatch.setenv("HOME", str(h))
    for k in [k for k in os.environ if k.startswith("GIT_")]:
        monkeypatch.delenv(k)


class Runs:
    """The example runner of the tests: python -I in a local process on the copy of the tree the job made; it counts its calls."""
    def __init__(self, fail=None):
        self.calls, self.fail, self.cfgs = 0, fail, []

    def __call__(self, tree, scfg):
        self.cfgs.append(scfg)

        def run(argv):
            self.calls += 1
            if self.fail:
                raise self.fail
            r = subprocess.run([sys.executable, *argv[1:]], capture_output=True, text=True, timeout=120, cwd=str(tree))
            return {"stdout": r.stdout, "stderr": r.stderr, "exit_code": r.returncode}
        return run, str(tree)


def start(env, issue, runs=None, job_id="jtest", **kw):
    env.runs = runs or Runs()
    env.deps.example_runner = env.runs
    return rj.start_code(repo=env.repo, commit="HEAD", issue=issue, cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs, job_id=job_id, **kw)


def review_ready(env, *examples, runs=None):
    start(env, issue_with(*examples), runs)
    env.approve()
    return env.job()


def audit_path(env, sid="a1"):
    return env.job().dir / f"examples_audit_{sid}.json"


def audit_json(env):
    return json.loads(audit_path(env).read_text())


def apply(env, sha=None, **kw):
    job = env.job()
    sha = sha or hashlib.sha256((Path(job.data["stages"]["a1"]["review"]["dir"]) / "changes.patch").read_bytes()).hexdigest()
    return ra.apply("jtest", sha[:12], deps=env.deps, jobs_dir=env.jobs, **kw)


def head(env):
    return subprocess.run(["git", "-C", str(env.repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()


def not_applied(env, before):
    assert head(env) == before and env.job().data["state"] == rj.REVIEW_READY
    assert subprocess.run(["git", "-C", str(env.repo), "status", "--porcelain"], capture_output=True, text=True).stdout == ""


@pytest.fixture
def env(tmp_path):
    return tr.Env(tmp_path)


# ---- the block --------------------------------------------------------------------------------------------------------

def test_the_block_is_read_from_the_issue_text_and_an_issue_without_one_has_no_gate():
    assert eg.extract(td.ISSUE) == (False, [], [])
    present, examples, problems = eg.extract(issue_with(SAME, AFTER))
    assert present and problems == [] and [e["id"] for e in examples] == ["e1", "e2"]
    assert eg.extract(None) == (False, [], [])


@pytest.mark.parametrize("text, why", [
    ("```argus-examples\nnot json\n```\n", "not JSON"),
    ("```argus-examples\n{}\n```\n", "non-empty list"),
    (block(SAME) + block(AFTER), "2 argus-examples blocks"),
    (block({**SAME, "wat": 1}), "unknown key"),
    ("```argus-examples\n[1]\n```\n", "must be an object"),
])
def test_a_block_that_is_not_usable_is_reported_never_raised(text, why):
    present, examples, problems = eg.extract(td.ISSUE + "\n" + text)
    assert present and examples == [] and why in " ".join(problems)


def test_a_python_fence_is_not_a_block_and_a_block_in_a_python_fence_is_not_either():
    assert eg.extract("```python\nprint(1)\n```\n")[0] is False
    assert eg.extract("```json\n[]\n```\n")[0] is False


def test_an_environment_runs_examples_unless_its_runner_is_not_python():
    cfg = {"sandbox": {"environments": {"py": {"image": None}, "node": {"image": None, "runner": "vitest"},
                                         "pt": {"runner": "pytest"}}}}
    assert [eg.no_runner(cfg, n) for n in (None, "py", "pt", "node", "unknown")] == [False, False, False, True, False]


# ---- intake: before any drafter money ----------------------------------------------------------------------------------

def test_examples_that_hold_let_the_job_reach_the_drafter_and_their_result_is_kept(env):
    job = start(env, issue_with(SAME, AFTER))
    assert job.data["state"] == rj.AWAITING_APPROVAL and env.drafter.calls
    rec = json.loads((job.dir / eg.INTAKE_FILE).read_text())
    got = {r["id"]: r for r in rec["results"]}
    assert got["e1"]["status"] == "pass" and got["e2"]["status"] == "unchecked" and got["e2"]["base_actual"] == -4
    text = rj.status("jtest", jobs_dir=env.jobs)
    assert "examples at base: e1 same: pass; e2 after: gives -4 now" in text and ex.RUN_LABEL in text
    env.approve()
    assert any("examples at base: e1 same: pass" in c for c in env.confirms)


def test_the_runner_gets_the_time_the_examples_need_and_the_jobs_environment(env):
    start(env, issue_with(SAME, AFTER))
    assert [c["timeout_s"] for c in env.runs.cfgs] == [ex.pass_timeout_s(2)] and ex.pass_timeout_s(2) == 55
    job = env.job()
    job.data["inputs"]["environment"] = "athena_py312"
    rj.example_runner(job, env.cfg, env.deps, "/t", 1)
    assert env.runs.cfgs[-1]["environment"] == "athena_py312"


def test_a_same_example_that_is_wrong_blocks_the_job_before_the_drafter_and_names_the_real_value(env):
    with pytest.raises(rj.Refused, match=r"example e1 \(same\) fail: expects 5; the code gave 4"):
        start(env, issue_with({**SAME, "expect": 5}))
    d = env.job().data
    assert d["state"] == rj.BLOCKED and "e1" in d["log"][-1]["reason"] and env.drafter.calls == [] and d["stages"] == {}
    assert "why: examples:" in rj.status("jtest", jobs_dir=env.jobs)


def test_an_example_that_raises_when_it_should_not_blocks_the_job(env):
    boom = {**SAME, "run": "total([2, 'x'], 1)"}
    with pytest.raises(rj.Refused, match="example e1 \\(same\\) error"):
        start(env, issue_with(boom))


def test_an_after_example_that_already_passes_on_the_base_is_refused_as_a_same(env):
    with pytest.raises(rj.Refused, match=r"example e2 \(after\) already passes on the base: it is a `same`"):
        start(env, issue_with({**AFTER, "run": "total([2, 3], 1)", "expect": 4}))
    assert env.job().data["state"] == rj.BLOCKED and env.drafter.calls == []


def test_an_example_that_calls_nothing_of_the_repository_is_refused_without_running_it(env):
    runs = Runs()
    with pytest.raises(rj.Refused, match="imports no module of the repository"):
        start(env, issue_with({**SAME, "setup": "r = 4", "run": "r"}), runs)
    assert runs.calls == 0


@pytest.mark.parametrize("text", ["```argus-examples\n[}\n```\n", block({**SAME, "tier": "now"}), block(SAME, SAME)])
def test_a_block_that_is_not_usable_blocks_the_job_without_running_anything(env, text):
    runs = Runs()
    with pytest.raises(rj.Refused, match="argus-examples block of the issue is not usable"):
        start(env, td.ISSUE + "\n" + text, runs)
    assert env.job().data["state"] == rj.BLOCKED and runs.calls == 0 and env.drafter.calls == []


def test_a_sandbox_that_is_not_available_blocks_the_job_as_such_and_is_not_a_verdict_on_the_examples(env):
    with pytest.raises(rj.Refused, match="sandbox is not available"):
        start(env, issue_with(SAME), Runs(fail=SandboxUnavailable("docker is down")))
    d = env.job().data
    assert d["state"] == rj.BLOCKED and d["log"][-1]["reason"].startswith("sandbox_unavailable") and env.drafter.calls == []


def test_a_crash_of_the_check_itself_blocks_the_job_and_never_lets_it_through(env):
    with pytest.raises(rj.Refused, match="could not be run"):
        start(env, issue_with(SAME), Runs(fail=RuntimeError("boom")))
    assert env.job().data["state"] == rj.BLOCKED and env.drafter.calls == []


def test_an_issue_without_the_block_runs_nothing_and_writes_nothing(env):
    runs = Runs()
    job = start(env, td.ISSUE, runs)
    assert runs.calls == 0 and not (job.dir / eg.INTAKE_FILE).exists() and job.data["state"] == rj.AWAITING_APPROVAL
    env.approve()
    assert not list(env.job().dir.glob("examples_*")) and "examples" not in rj.status("jtest", jobs_dir=env.jobs)


def test_an_environment_without_an_example_runner_is_noted_and_not_asked_for_results(env):
    env.cfg["sandbox"] = {"environments": {"viewer": {"image": None, "runner": "vitest"}}}
    job = start(env, issue_with(SAME), runs=None)
    job.data["inputs"]["environment"] = "viewer"
    job.save()
    job.data["state"] = rj.NEW
    runs = Runs()
    env.deps.example_runner = runs
    rj._example_gate(job, env.cfg, env.deps)
    assert runs.calls == 0 and json.loads((job.dir / eg.INTAKE_FILE).read_text())["skipped"] == eg.RUNNER_NOTE
    assert "not run (environment without an example runner)" in "\n".join(rj.example_lines(job))


# ---- the check on the base, without a job: whatif and the other tiers ------------------------------------------------------

def whatif(**kw):
    base = {"id": "e1", "tier": "whatif", "says": "With a floor of 60 a price of 55 is blocked", "setup": "from shop.rules import blocked",
            "run": "blocked(55.0)", "expect": True, "overrides": {"shop.rules.FLOOR": 60.0}}
    return {**base, **kw}


def local_runner(tree):
    def run(argv):
        r = subprocess.run([sys.executable, *argv[1:]], capture_output=True, text=True, timeout=120, cwd=tree)
        return {"stdout": r.stdout, "stderr": r.stderr, "exit_code": r.returncode}
    return run


def check(tmp_path, *examples):
    tree = make_tree(tmp_path)
    return eg.check_base(list(examples), tree, local_runner(tree), root=tree)


def test_a_whatif_that_changes_what_the_example_sees_passes_with_its_override(tmp_path):
    results, problems = check(tmp_path, whatif())
    assert problems == [] and results[0]["status"] == "pass"


def test_a_whatif_whose_override_changes_nothing_is_refused_and_names_who_else_holds_the_name(tmp_path):
    same_both_ways = whatif(run="blocked(10.0)", expect=True)           # 10 is blocked with a floor of 50 and of 60
    results, problems = check(tmp_path, same_both_ways)
    assert len(problems) == 1 and "the override changes nothing the example sees" in problems[0]
    by_value = whatif(id="e3", setup="from shop.user import floor_here", run="floor_here()", expect=50.0)   # user.py read FLOOR by value
    results, problems = check(tmp_path, by_value)
    assert len(problems) == 1 and "changes nothing" in problems[0] and "shop/consts.py" in problems[0]    # the module that really holds it


def test_a_whatif_that_fails_with_its_override_is_a_problem_with_the_real_value(tmp_path):
    results, problems = check(tmp_path, whatif(expect=False))
    assert "example e1 (whatif) fail: expects false; the code gave true" in problems[0]


def test_an_after_example_is_run_for_information_and_is_unchecked_in_the_result(tmp_path):
    after = {"id": "e1", "tier": "after", "says": "A floor of 50 blocks 50", "setup": "from shop.rules import stop", "run": "stop(100.0, 40.0)", "expect": 1}
    results, problems = check(tmp_path, after)
    assert problems == [] and results == [{"id": "e1", "tier": "after", "status": "unchecked", "base_actual": 50.0}]


def test_the_audit_runs_a_whatif_without_its_overrides_and_every_tier(tmp_path):
    tree = make_tree(tmp_path)
    ex1 = whatif(run="blocked(55.0)", expect=False)                        # false with the real floor of 50: what the patch is meant to keep
    res = eg.audit([ex1], local_runner(tree), root=tree)
    assert [(r["id"], r["status"]) for r in res] == [("e1", "pass")]
    res = eg.audit([whatif()], local_runner(tree), root=tree)               # the override is NOT applied at the audit
    assert res[0]["status"] == "fail" and res[0]["actual"] is False


# ---- the audit after the agent --------------------------------------------------------------------------------------------

def test_the_audit_runs_on_the_final_code_and_is_bound_to_the_patch_and_the_examples(env):
    job = review_ready(env, SAME, AFTER)
    rec = audit_json(env)
    sha = job.data["stages"]["a1"]["review"]["patch_sha256"]
    assert rec["key"] == eg.audit_key(sha, eg.extract(job.data["inputs"]["issue"])[1]) and rec["skipped"] is None
    assert {r["id"]: r["status"] for r in rec["results"]} == {"e1": "pass", "e2": "pass"}      # e2: total([1], 5) is 0 now
    assert "examples after the agent: e1 same: pass; e2 after: pass" in rj.status("jtest", jobs_dir=env.jobs)


def test_an_example_the_agent_did_not_make_true_is_a_failed_result_with_what_the_code_gave(env):
    review_ready(env, SAME, WRONG_AFTER)
    got = {r["id"]: r for r in audit_json(env)["results"]}
    assert got["e2"]["status"] == "fail" and got["e2"]["actual"] == 0
    text = rj.status("jtest", jobs_dir=env.jobs)
    assert "examples failed: e2; `argus apply` refuses unless you give --allow-failed-examples e2" in text


def test_an_audit_that_cannot_run_leaves_a_pending_marker_and_the_job_review_ready(env):
    runs = Runs()
    start(env, issue_with(SAME), runs)
    runs.fail = SandboxUnavailable("docker is down")
    job, r = env.approve()
    assert r["status"] == "DONE" and job.data["state"] == rj.REVIEW_READY
    rec = audit_json(env)
    assert rec["results"] is None and rec["skipped"] is None and rec["reason"] == "the sandbox is not available"
    assert "NOT FINISHED (the sandbox is not available); `argus apply` refuses it: `argus resume jtest` runs it again" in rj.status(
        "jtest", jobs_dir=env.jobs)


def test_an_audit_cut_off_by_an_interrupt_leaves_the_pending_marker_and_apply_refuses(env):
    runs = Runs()
    start(env, issue_with(SAME), runs)
    runs.fail = KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        env.approve()
    assert env.job().data["state"] == rj.REVIEW_READY and audit_json(env)["results"] is None
    with pytest.raises(rj.Refused, match="did not finish"):
        apply(env)


def test_the_decision_is_for_the_patch_the_caller_holds_not_the_one_on_disk_at_another_time(env):
    review_ready(env, SAME)
    job = env.job()
    assert rj.examples_decision(job) == []
    with pytest.raises(rj.Refused, match="another patch or other examples"):
        rj.examples_decision(job, sha="0" * 64)


def test_resume_runs_the_audit_again_and_a_second_failure_refuses_and_changes_nothing(env):
    runs = Runs()
    start(env, issue_with(SAME), runs)
    runs.fail = SandboxUnavailable("docker is down")
    env.approve()
    with pytest.raises(rj.Refused, match=r"the examples audit did not finish \(the sandbox is not available\)"):
        rj.resume("jtest", cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs)
    assert audit_json(env)["results"] is None
    runs.fail = None
    job, r = rj.resume("jtest", cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs)
    assert r == {"kind": "examples", "status": "AUDITED"} and job.data["state"] == rj.REVIEW_READY
    assert [x["status"] for x in audit_json(env)["results"]] == ["pass"]
    with pytest.raises(rj.Refused, match="nothing to resume"):                            # a finished audit is not run again
        rj.resume("jtest", cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs)


def test_resume_of_a_job_without_the_block_has_nothing_to_do(env):
    start(env, td.ISSUE)
    env.approve()
    with pytest.raises(rj.Refused, match="nothing to resume"):
        rj.resume("jtest", cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs)


def test_a_patch_that_does_not_apply_to_the_base_is_a_pending_audit_with_that_reason(env):
    review_ready(env, SAME)
    job = env.job()
    (Path(job.data["stages"]["a1"]["review"]["dir"]) / "changes.patch").write_text("not a patch\n")
    assert rj._examples_audit(job, "a1", env.cfg, env.deps) is False
    assert audit_json(env)["reason"] == "the patch does not apply to the base"


def test_the_audit_never_raises_into_the_agent_stage(env):
    start(env, issue_with(SAME))
    env.deps.example_runner = lambda tree, scfg: (_ for _ in ()).throw(KeyError("x"))
    job, r = env.approve()
    assert r["status"] == "DONE" and job.data["state"] == rj.REVIEW_READY and audit_json(env)["reason"] == "KeyError"


def test_an_environment_without_a_runner_stores_a_skipped_audit(env):
    review_ready(env, SAME)
    job = env.job()
    env.cfg["sandbox"] = {"environments": {"viewer": {"image": None, "runner": "vitest"}}}
    job.data["inputs"]["environment"] = "viewer"
    assert rj._examples_audit(job, "a1", env.cfg, env.deps) is True
    assert audit_json(env)["skipped"] == eg.RUNNER_NOTE


# ---- apply and applied --------------------------------------------------------------------------------------------------

def test_a_job_whose_examples_pass_is_applied_and_the_record_has_no_examples_field(env):
    review_ready(env, SAME, AFTER)
    done = apply(env)
    assert done.data["state"] == rj.APPLIED
    assert all("examples_failed" not in e for e in done.data["log"])


def test_a_failed_example_refuses_apply_by_id_and_nothing_changes(env):
    review_ready(env, SAME, WRONG_AFTER)
    before = head(env)
    with pytest.raises(rj.Refused, match=r"examples failed on this patch: e2; to apply it anyway name exactly these: --allow-failed-examples e2"):
        apply(env)
    not_applied(env, before)
    assert not any(e["what"] == "apply_started" for e in env.job().data["log"])


def test_allowing_exactly_the_failed_ids_applies_and_records_them_on_the_existing_entries(env):
    review_ready(env, SAME, WRONG_AFTER)
    done = apply(env, allow_failed_examples=("e2",))
    log = done.data["log"]
    assert done.data["state"] == rj.APPLIED
    assert [e["examples_failed"] for e in log if e["what"] in ("apply_started",)] == [["e2"]]
    assert log[-1]["what"] == "state" and log[-1]["new"] == rj.APPLIED and log[-1]["examples_failed"] == ["e2"]
    assert not [e["what"] for e in log if "example" in e["what"]]                       # no new kind of entry: the job stays projectable


@pytest.mark.parametrize("allow", [("e1",), ("e1", "e2"), ("e3",), ()])
def test_the_flag_must_name_exactly_the_failed_ids(env, allow):
    review_ready(env, SAME, WRONG_AFTER)
    before = head(env)
    with pytest.raises(rj.Refused, match="--allow-failed-examples e2|exactly these"):
        apply(env, allow_failed_examples=allow)
    not_applied(env, before)


def test_the_flag_on_a_job_where_nothing_failed_is_refused(env):
    review_ready(env, SAME)
    before = head(env)
    with pytest.raises(rj.Refused, match=r"--allow-failed-examples names e1, but no example failed on this patch"):
        apply(env, allow_failed_examples=("e1",))
    not_applied(env, before)


def test_a_missing_pending_or_stale_result_refuses_apply_and_points_at_resume(env):
    review_ready(env, SAME)
    before = head(env)
    good = audit_path(env).read_text()
    audit_path(env).unlink()
    with pytest.raises(rj.Refused, match="were not run on this patch; run `argus resume jtest` first"):
        apply(env)
    not_applied(env, before)
    rec = json.loads(good)
    audit_path(env).write_text(json.dumps({**rec, "results": None, "reason": "x"}))
    with pytest.raises(rj.Refused, match="did not finish"):
        apply(env)
    audit_path(env).write_text(json.dumps({**rec, "key": "0" * 64}))
    with pytest.raises(rj.Refused, match="another patch or other examples"):
        apply(env)
    audit_path(env).write_text("{not json")
    with pytest.raises(rj.Refused, match="cannot be read"):
        apply(env)
    not_applied(env, before)


def test_a_result_for_another_patch_is_stale_even_when_it_passed(env):
    review_ready(env, SAME)
    job = env.job()
    d = Path(job.data["stages"]["a1"]["review"]["dir"])
    patch = (d / "changes.patch").read_bytes().replace(b"max(sum(prices) - discount, 0)", b"max(sum(prices) - discount, 0) ")
    (d / "changes.patch").write_bytes(patch)
    sha = hashlib.sha256(patch).hexdigest()
    prov = json.loads((d / "provenance.json").read_text())
    prov["patch"]["sha256"] = sha
    (d / "provenance.json").write_text(json.dumps(prov))
    job.data["stages"]["a1"]["review"]["patch_sha256"] = sha
    job.save()
    with pytest.raises(rj.Refused, match="another patch or other examples"):
        apply(env, sha)


def test_results_that_are_not_exactly_the_issues_examples_read_as_unreadable(env):
    review_ready(env, SAME, AFTER)
    rec = audit_json(env)
    for results in (rec["results"][:1], rec["results"] + [{"id": "e9", "tier": "same", "status": "pass"}],
                    [{**rec["results"][0], "status": "great"}, rec["results"][1]]):
        audit_path(env).write_text(json.dumps({**rec, "results": results}))
        with pytest.raises(rj.Refused, match="cannot be read"):
            apply(env)


def test_a_block_that_cannot_be_parsed_at_apply_refuses_it(env):
    review_ready(env, SAME)
    job = env.job()
    job.data["inputs"]["issue"] = td.ISSUE + "\n```argus-examples\nnot json\n```\n"
    job.save()
    with pytest.raises(rj.Refused, match="argus-examples block of the issue is not usable"):
        apply(env)


def test_a_job_from_before_the_gate_has_no_gate_and_is_applied(env):
    start(env, td.ISSUE)
    env.approve()
    assert not list(env.job().dir.glob("examples_*"))
    assert apply(env).data["state"] == rj.APPLIED


def test_an_environment_without_a_runner_is_applied_on_its_skipped_result(env):
    review_ready(env, SAME)
    eg.store(audit_path(env), audit_json(env)["key"], skipped=eg.RUNNER_NOTE)
    assert apply(env).data["state"] == rj.APPLIED


def test_a_crash_after_the_commit_is_healed_with_the_same_flag_and_records_it(env, monkeypatch):
    review_ready(env, SAME, WRONG_AFTER)
    real = rj._record_applied
    calls = []

    def die_once(*a, **k):
        calls.append(k.get("allow_failed_examples"))
        if len(calls) == 1:
            raise KeyboardInterrupt
        return real(*a, **k)
    monkeypatch.setattr(rj, "_record_applied", die_once)
    with pytest.raises(KeyboardInterrupt):
        apply(env, allow_failed_examples=("e2",))
    done = apply(env, allow_failed_examples=("e2",))
    assert done.data["state"] == rj.APPLIED and done.data["log"][-1]["examples_failed"] == ["e2"] and calls == [("e2",), ("e2",)]


def test_applied_by_hand_is_gated_by_the_same_rule(env):
    review_ready(env, SAME, WRONG_AFTER)
    commit = head(env)
    with pytest.raises(rj.Refused, match="examples failed on this patch: e2"):
        rj.applied("jtest", commit, deps=env.deps, jobs_dir=env.jobs)
    assert env.job().data["state"] == rj.REVIEW_READY
    with pytest.raises(rj.Refused, match="no example failed|exactly these"):
        rj.applied("jtest", commit, deps=env.deps, jobs_dir=env.jobs, allow_failed_examples=("e1",))
    done = rj.applied("jtest", commit, deps=env.deps, jobs_dir=env.jobs, allow_failed_examples=("e2",))
    assert done.data["state"] == rj.APPLIED and done.data["log"][-1]["examples_failed"] == ["e2"]


def test_applied_by_hand_refuses_a_pending_audit_and_passes_a_clean_one_without_a_field(env):
    review_ready(env, SAME)
    good = audit_path(env).read_text()
    audit_path(env).write_text(json.dumps({**json.loads(good), "results": None}))
    with pytest.raises(rj.Refused, match="did not finish"):
        rj.applied("jtest", head(env), deps=env.deps, jobs_dir=env.jobs)
    audit_path(env).write_text(good)
    done = rj.applied("jtest", head(env), deps=env.deps, jobs_dir=env.jobs)
    assert done.data["state"] == rj.APPLIED and "examples_failed" not in done.data["log"][-1]


# ---- the command line -------------------------------------------------------------------------------------------------------

def test_the_cli_takes_the_flag_on_apply_and_applied_and_refuses_a_bad_id(env, capsys):
    sys.path.insert(0, str(tr.ROOT / "scripts"))
    import argus
    review_ready(env, SAME, WRONG_AFTER)
    sha = hashlib.sha256((Path(env.job().data["stages"]["a1"]["review"]["dir"]) / "changes.patch").read_bytes()).hexdigest()[:12]
    base = ["--jobs-dir", str(env.jobs)]
    assert argus.main([*base, "apply", "jtest", "--read-sha", sha], deps=env.deps) == 2
    assert "examples failed on this patch: e2" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        argus.main([*base, "apply", "jtest", "--read-sha", sha, "--allow-failed-examples", "e2;rm"], deps=env.deps)
    assert argus.main([*base, "apply", "jtest", "--read-sha", sha, "--allow-failed-examples", "e2"], deps=env.deps) == 0
    assert env.job().data["state"] == rj.APPLIED


# ---- the public snapshot and what a model can reach --------------------------------------------------------------------------

def test_a_job_with_example_data_projects_to_the_public_snapshot_as_any_other(env):
    review_ready(env, SAME, WRONG_AFTER)
    raw = json.loads(json.dumps(apply(env, allow_failed_examples=("e2",)).data))
    plain = stage_data.project_job(raw, "jtest")                         # the whole log: repro and apply_started are known kinds now
    assert plain["state"] == rj.APPLIED and "examples" not in json.dumps(plain)


def test_what_the_examples_printed_is_cleaned_before_it_is_stored_and_shown(env):
    evil = {**SAME, "id": "e3", "run": "total([1], 1) and '\\x1b[31mred\\x00'", "expect": "x"}
    with pytest.raises(rj.Refused) as e:
        start(env, issue_with(SAME, evil))
    assert "\x1b" not in str(e.value) and "\x00" not in str(e.value) and "\x1b" not in env.job().data["log"][-1]["reason"]


# ---- gaps the mutants found -----------------------------------------------------------------------------------------------

def test_a_block_with_one_good_and_one_bad_example_gives_no_examples_at_all():
    present, examples, problems = eg.extract(td.ISSUE + "\n" + block(SAME, {**AFTER, "tier": "now"}))
    assert present and examples == [] and problems


def test_failing_counts_every_status_but_pass():
    rs = [{"id": f"e{i}", "tier": "same", "status": s} for i, s in enumerate(("pass", "fail", "error", "invalid", "unchecked"), 1)]
    assert eg.failing(rs) == ["e2", "e3", "e4", "e5"]


def test_a_result_for_other_examples_or_another_base_is_stale(env):
    review_ready(env, SAME)
    job = env.job()
    job.data["inputs"]["issue"] = issue_with({**SAME, "expect": 5})              # the examples changed after the audit
    with pytest.raises(rj.Refused, match="another patch or other examples"):
        rj.examples_decision(job)
    job = env.job()
    job.data["intake"]["snapshot_sha256"] = "0" * 64                              # the base changed after the intake
    assert "not run for this issue or base" in "\n".join(rj.example_lines(job))


def test_an_audit_result_of_error_refuses_apply(env):
    review_ready(env, SAME)
    rec = audit_json(env)
    rec["results"][0].update(status="error", actual="<no result>")
    audit_path(env).write_text(json.dumps(rec))
    with pytest.raises(rj.Refused, match="examples failed on this patch: e1"):
        apply(env)


def test_a_package_that_is_not_valid_is_not_audited(env):
    review_ready(env, SAME)
    job = env.job()
    audit_path(env).unlink()
    job.data["stages"]["a1"]["review"]["valid"] = False
    assert rj._examples_audit(job, "a1", env.cfg, env.deps) is None and not audit_path(env).exists()


def test_the_cli_takes_the_flag_on_applied(env):
    sys.path.insert(0, str(tr.ROOT / "scripts"))
    import argus
    review_ready(env, SAME, WRONG_AFTER)
    base = ["--jobs-dir", str(env.jobs), "applied", "jtest", "--commit", head(env)]
    assert argus.main(base, deps=env.deps) == 2 and env.job().data["state"] == rj.REVIEW_READY
    assert argus.main([*base, "--allow-failed-examples", "e2"], deps=env.deps) == 0
    assert env.job().data["state"] == rj.APPLIED and env.job().data["log"][-1]["examples_failed"] == ["e2"]


# ---- the review of PR 2 (Opus) ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "```argus-examples json\n[]\n```\n",                               # an info string with more than the word
    "```Argus-Examples\n[]\n```\n",                                    # another case is still a block (read, then judged on its content)
    "```argus-examples\n[]\n",                                        # never closed
    "``` argus-examples extra\n[]\n```\n",
])
def test_a_fence_that_names_the_block_but_is_not_exact_is_never_read_as_no_block(text):
    present, examples, problems = eg.extract(td.ISSUE + "\n" + text)
    assert present and examples == [] and problems


def test_crlf_line_ends_and_a_longer_closing_fence_are_the_block():
    text = (td.ISSUE + "\n\n```argus-examples\n" + json.dumps([SAME]) + "\n````\n").replace("\n", "\r\n")
    present, examples, problems = eg.extract(text)
    assert present and problems == [] and [e["id"] for e in examples] == ["e1"]


def test_a_block_nested_far_too_deep_is_a_problem_not_a_crash():
    present, examples, problems = eg.extract("```argus-examples\n" + "[" * 200000 + "\n```\n")
    assert present and examples == [] and problems


def test_a_near_miss_fence_blocks_the_job_at_intake(env):
    with pytest.raises(rj.Refused, match="not usable"):
        start(env, td.ISSUE + "\n```argus-examples json\n[]\n```\n")
    assert env.job().data["state"] == rj.BLOCKED


def test_a_pass_that_printed_nothing_is_a_failed_container_not_a_verdict(env, tmp_path):
    class Silent(Runs):
        def __call__(self, tree, scfg):
            return (lambda argv: {"stdout": "", "stderr": "", "exit_code": 125}), str(tree)
    with pytest.raises(rj.Refused, match="sandbox is not available"):
        start(env, issue_with(SAME), Silent())
    assert env.job().data["log"][-1]["reason"].startswith("sandbox_unavailable")
    runs = Runs()
    env2 = tr.Env(tmp_path / "two")
    start(env2, issue_with(SAME), runs)
    runs.__class__ = Silent                                            # the container fails at the audit: pending, resumable
    env2.deps.example_runner = Silent()
    env2.approve()
    assert json.loads((env2.job().dir / "examples_audit_a1.json").read_text())["results"] is None
    env2.deps.example_runner = Runs()
    job, r = rj.resume("jtest", cfg=env2.cfg, deps=env2.deps, jobs_dir=env2.jobs)
    assert r["status"] == "AUDITED"


def test_the_production_runner_turns_a_docker_failure_into_sandbox_unavailable(env, monkeypatch):
    from tools import sandbox
    start(env, td.ISSUE)
    env.deps.example_runner = None
    answers = [{"exit_code": 125, "stdout": ""}, {"exit_code": 0, "stdout": "ok", "cleanup_failed": True}, {"exit_code": 0, "stdout": "ok"}]
    monkeypatch.setattr(sandbox, "run_command", lambda argv, workdir, cfg: answers.pop(0))
    run, root = rj.example_runner(env.job(), env.cfg, env.deps, "/t", 1)
    assert root == "/workspace"
    for _ in range(2):
        with pytest.raises(SandboxUnavailable):
            run(["python3"])
    assert run(["python3"])["stdout"] == "ok"


def test_the_block_output_in_a_blocked_reason_carries_the_data_label(env):
    with pytest.raises(rj.Refused) as e:
        start(env, issue_with({**SAME, "expect": 5}))
    assert ex.RUN_LABEL in str(e.value) and ex.RUN_LABEL in env.job().data["log"][-1]["reason"]


def test_the_audit_is_keyed_on_the_bytes_it_applied(env):
    review_ready(env, SAME)
    job = env.job()
    d = Path(job.data["stages"]["a1"]["review"]["dir"])
    assert audit_json(env)["key"] == eg.audit_key(hashlib.sha256((d / "changes.patch").read_bytes()).hexdigest(),
                                                  eg.extract(job.data["inputs"]["issue"])[1])


def test_resume_runs_a_missing_stale_or_damaged_audit_again(env):
    review_ready(env, SAME)
    good = audit_path(env).read_text()
    for bad in (None, json.dumps({**json.loads(good), "key": "0" * 64}), "{nope"):
        audit_path(env).unlink()
        if bad is not None:
            audit_path(env).write_text(bad)
        job, r = rj.resume("jtest", cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs)
        assert r["status"] == "AUDITED" and json.loads(audit_path(env).read_text())["key"] == json.loads(good)["key"]


def test_apply_and_applied_hand_the_sha_they_hold_to_the_decision(env, monkeypatch):
    review_ready(env, SAME)
    seen = []
    real = rj.examples_decision
    monkeypatch.setattr(rj, "examples_decision", lambda job, allow=(), sha=None: (seen.append(sha), real(job, allow, sha=sha))[1])
    job = env.job()
    sha = hashlib.sha256((Path(job.data["stages"]["a1"]["review"]["dir"]) / "changes.patch").read_bytes()).hexdigest()
    apply(env)
    assert seen and all(x == sha for x in seen) and len(seen) == 2          # at apply, and again where it is recorded


def test_what_is_read_back_from_a_result_file_is_cleaned_again(env):
    review_ready(env, SAME)
    rec = audit_json(env)
    rec["results"][0]["actual"] = "a\x1b[31mb\x00c"
    audit_path(env).write_text(json.dumps(rec))
    kind, val = rj.examples_audit_state(env.job())
    assert kind == "results" and "\x1b" not in val[0]["actual"] and "\x00" not in val[0]["actual"]
    audit_path(env).write_text(json.dumps({**rec, "results": None, "reason": "x\x1b[0my"}))
    assert "\x1b" not in rj.examples_audit_state(env.job())[1]
    audit_path(env).write_text(json.dumps({**rec, "skipped": "why\x1b[0m"}))
    assert "\x1b" not in rj.examples_audit_state(env.job())[1]


def test_the_ids_of_the_flag_are_e1_to_e99_only():
    sys.path.insert(0, str(tr.ROOT / "scripts"))
    import argus
    import argparse
    assert argus._ids("e1, e99") == ("e1", "e99")
    for bad in ("e0", "e100", "x", "", "E1"):
        with pytest.raises(argparse.ArgumentTypeError):
            argus._ids(bad)


def test_the_modules_named_as_other_holders_never_include_the_modules_own_file(tmp_path):
    tree = make_tree(tmp_path)
    holders = eg._holders(tree, whatif(overrides={"shop.consts.FLOOR": 60.0}))
    assert "shop/consts.py" not in holders and "shop/rules.py" in holders


# ---- the three mutants that survived the first run -----------------------------------------------------------------------

def test_a_block_in_capitals_is_read_as_the_block_and_gated():
    text = td.ISSUE + "\n```ARGUS-EXAMPLES\n" + json.dumps([SAME]) + "\n```\n"
    present, examples, problems = eg.extract(text)
    assert present and problems == [] and [e["id"] for e in examples] == ["e1"]


def test_the_result_file_is_written_through_a_temporary_file_and_a_rename(tmp_path, monkeypatch):
    calls = []
    real = os.replace
    monkeypatch.setattr(eg.os, "replace", lambda a, b: (calls.append((Path(a).name, Path(b).name)), real(a, b))[1])
    eg.store(tmp_path / "r.json", "k", results=[])
    assert calls == [("r.json.tmp", "r.json")] and not (tmp_path / "r.json.tmp").exists()


def test_the_audit_key_is_the_sha_of_the_bytes_that_were_applied_not_of_a_second_read(env, monkeypatch):
    review_ready(env, SAME)
    job = env.job()
    d = Path(job.data["stages"]["a1"]["review"]["dir"])
    want = eg.audit_key(hashlib.sha256((d / "changes.patch").read_bytes()).hexdigest(), eg.extract(job.data["inputs"]["issue"])[1])
    audit_path(env).unlink()
    monkeypatch.setattr(rj.repro, "patch_sha", lambda p: "f" * 64)              # a second read that sees something else
    assert rj._examples_audit(job, "a1", env.cfg, env.deps) is True and audit_json(env)["key"] == want
