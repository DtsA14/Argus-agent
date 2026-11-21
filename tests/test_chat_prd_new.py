"""P2a (SPEC_CHAT_MANAGER 13.2, 13.3, 13.8, 13.9): a PRD job typed by the human, from the chat. A real server on a free port; the CLI is a
recorder; the config is the repository's own, so the card is what the terminal's go-live screen would show."""
import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_chat_actions as t  # noqa: E402
from router import chat_actions as ca  # noqa: E402
from router import job as rj  # noqa: E402
from router import prd_job as pj  # noqa: E402
from runner import load_config  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BASE = load_config(ROOT / "config.yaml")
MSG = "Tambah ringkasan mingguan di halaman Progress dan jelaskan alasannya."
REPO = next(iter(BASE["issue_writer"]["repos"]))


def config(**over):
    c = copy.deepcopy(BASE)
    c["chat"] = {"daily_cap_usd": 2.0}
    c.update(over)
    return c


@pytest.fixture
def svc(tmp_path):
    s = t.Service(tmp_path, cfg=config())
    yield s
    s.stop()


def prep(svc, **kw):
    return svc.prepare(**{"action": "prd_new", "repo": REPO, "message": MSG, **kw})


def make_prd(jobs, job_id, via="ui", created=t.NOW - 100, max_usd=1.5, kind="prd"):
    d = jobs / job_id
    d.mkdir(parents=True)
    (d / "job.json").write_text(json.dumps({"job": job_id, "kind": kind, "state": "AWAITING_HUMAN", "max_usd": max_usd,
                                            "created_at": t.iso(created),
                                            "log": [{"at": t.iso(created), "what": "created", **({"via": via} if via else {})}]}))


# ---- the card ----------------------------------------------------------------------------------------------------------------

def test_prepare_shows_the_screen_facts_and_runs_nothing(svc):
    status, out = prep(svc)
    assert status == 200 and svc.spawner.calls == []
    card = out["card"]
    f = pj.screen_facts(svc.actions.cfg, BASE["issue_writer"]["repos"][REPO].get("environment"))
    assert card["action"] == "prd_new" and card["repo"] == REPO and card["message"] == MSG
    assert card["model"] == f["model"] and card["turn_cap_usd"] == f["turn_cap"]            # one function for the screen and the card
    assert card["job_cap_usd"] == float(BASE["prd_writer"]["max_usd"]) and card["commit"] == "HEAD when the job is created"
    assert ("runs_code" in card) == f["has_runner"]
    assert out["exposure_usd"] == card["job_cap_usd"]


@pytest.mark.parametrize("body", [
    {"ref": "other"}, {"max_usd": "9"}, {"rebase": "1"}, {"profile": "x"}, {"job": "j20261115_100000_aaaa"}, {"sha": "abc"}])
def test_the_card_takes_the_repo_and_the_message_and_nothing_else(svc, body):
    status, out = prep(svc, **body)
    assert status == 400 and "token" not in out and svc.spawner.calls == []


@pytest.mark.parametrize("over", [
    {"repo": "not-a-repo"}, {"repo": ""}, {"message": ""}, {"message": "x" * 5000},
    {"message": "key sk-ant-api03-" + "a" * 40}, {"message": "hidden​text in the message"}])
def test_a_bad_repo_or_message_gets_no_card(svc, over):
    status, out = prep(svc, **over)
    assert status == 400 and "token" not in out


def test_no_writer_key_means_no_card(tmp_path):
    s = t.Service(tmp_path, cfg=config(), environ={})
    try:
        status, out = prep(s)
        assert status == 409 and "token" not in out
    finally:
        s.stop()


def test_a_config_without_the_prd_writer_gets_no_card(tmp_path):
    c = config()
    del c["prd_writer"]
    s = t.Service(tmp_path, cfg=c)
    try:
        status, out = prep(s)
        assert status == 409 and "token" not in out
    finally:
        s.stop()


# ---- confirm: the argv ---------------------------------------------------------------------------------------------------------

def test_confirm_starts_prd_new_with_the_flags_the_chat_owns(svc):
    token = prep(svc)[1]["token"]
    status, out = svc.confirm(token)
    assert status == 200 and out["started"] is True and ca.UI_ID.fullmatch(out["job"])
    (call,) = svc.spawner.calls
    argv = call["argv"]
    assert argv[argv.index("prd") + 1] == "new" and call["action"] == "prd" and call["job"] == out["job"]
    assert argv[argv.index("--via") + 1] == "ui" and argv[argv.index("--job-id") + 1] == out["job"]
    assert argv[argv.index("--key-file") + 1] == t.WKEY and "--yes" in argv                # the writer's key slot, not the code key
    assert argv[argv.index("--repo") + 1] == REPO and "--message-file" in argv and MSG not in " ".join(argv)
    assert "--queues-dir" in argv and argv.index("--queues-dir") < argv.index("prd")        # the repository's state check reads the queues
    for never in ("--ref", "--rebase", "--max-usd", "--profile"):
        assert never not in argv
    assert call["text"] == MSG


def test_a_token_works_once_and_confirm_rebuilds_the_card(svc):
    token = prep(svc)[1]["token"]
    assert svc.confirm(token)[0] == 200
    assert svc.confirm(token)[0] == 403 and len(svc.spawner.calls) == 1


# ---- the money -------------------------------------------------------------------------------------------------------------------

def test_a_prd_job_started_from_the_ui_counts_as_exposure(svc):
    make_prd(svc.jobs, "j20261115_100000_aaaa")
    make_prd(svc.jobs, "j20261115_110000_aaaa", via="cli")                    # not from the UI
    make_prd(svc.jobs, "j20261113_100000_aaaa", created=t.NOW - 3600 * 60)    # two days ago
    assert svc.actions.exposure() == pytest.approx(float(BASE["prd_writer"]["max_usd"]))


def test_a_prd_job_counts_at_least_the_configured_cap(svc):
    make_prd(svc.jobs, "j20261115_100000_aaaa", max_usd=0.1)
    assert svc.actions.exposure() == pytest.approx(float(BASE["prd_writer"]["max_usd"]))


def test_the_audit_net_counts_a_confirmed_prd_job_whose_via_is_missing(svc):
    token = prep(svc)[1]["token"]
    job = svc.confirm(token)[1]["job"]
    svc.actions.pending.clear()                                               # what a restart forgets
    make_prd(svc.jobs, job, via=None, created=t.NOW)                           # the CLI wrote a job but lost its `via`
    assert svc.actions.exposure() == pytest.approx(float(BASE["prd_writer"]["max_usd"]))


def test_a_prd_is_refused_when_the_cap_would_be_passed(svc):
    make_prd(svc.jobs, "j20261115_100000_aaaa")
    status, out = prep(svc)                                                   # 1.5 + 1.5 > 2.0
    assert status == 403 and "daily cap" in out["refused"] and "token" not in out and svc.spawner.calls == []


def test_two_confirms_back_to_back_cannot_beat_the_cap(svc):
    a = prep(svc)[1]["token"]
    b = prep(svc)[1]["token"]                                                 # both prepared before either runs: 1.5 each
    assert svc.confirm(a)[0] == 200
    status, out = svc.confirm(b)
    assert status == 403 and "daily cap" in out["refused"] and len(svc.spawner.calls) == 1


# ---- an action with no branch never starts another one ------------------------------------------------------------------

def test_an_unknown_action_is_never_dispatched_to_issue_start(svc):
    with pytest.raises(ca.Refusal) as e:
        svc.actions.execute("not_an_action", {"action": "x", "job_cap_usd": 0}, {"job": "j20261115_100000_aaaa", "sha": "abc"})
    assert e.value.status == 500 and svc.spawner.calls == []


def test_every_action_has_a_branch_in_execute(svc):
    import inspect
    src = inspect.getsource(ca.Actions.execute)
    for a in ca.ACTIONS:
        assert f'"{a}"' in src, a


# ---- the CLI side: --via, the id, the screen -------------------------------------------------------------------------------

def test_prd_new_via_must_be_a_known_place_and_the_id_a_harness_id(tmp_path):
    import test_prd_writer as w
    env = w.Env(tmp_path, [w.submit()])
    kw = dict(repo="demo", message=w.FIRST, cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs, queues_dir=env.queues)
    with pytest.raises(rj.Refused, match="via"):
        pj.new(**kw, job_id="j20261116_120000_ab12", via="elsewhere")
    with pytest.raises(rj.Refused, match="shape"):
        pj.new(**kw, job_id="jp", via="ui")                                     # a chat-started id is the exact shape, now
    with pytest.raises(rj.Refused, match="within"):
        pj.new(**kw, job_id="j20261116_130000_ab12", via="ui")                  # an hour off
    assert not list(env.jobs.glob("j*")) and env.model.calls == []


def test_prd_new_via_ui_is_written_to_the_created_note(tmp_path):
    import test_prd_writer as w
    env = w.Env(tmp_path, [w.submit()])
    job = pj.new(repo="demo", message=w.FIRST, cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs, queues_dir=env.queues,
                 job_id="j20261116_120000_ab12", via="ui")
    created = [e for e in job.data["log"] if e.get("what") == "created"]
    assert len(created) == 1 and created[0].get("via") == "ui"


def test_prd_new_without_via_writes_none(tmp_path):
    import test_prd_writer as w
    env = w.Env(tmp_path, [w.submit()])
    job = env.new()
    assert [e for e in job.data["log"] if e.get("what") == "created"][0].get("via") is None


def test_a_job_id_with_a_trailing_newline_is_refused(tmp_path):
    import test_prd_writer as w
    env = w.Env(tmp_path, [w.submit()])
    with pytest.raises(rj.Refused, match="not a job id"):
        pj.new(repo="demo", message=w.FIRST, cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs, queues_dir=env.queues, job_id="jp\n")
    assert env.model.calls == []


def test_the_terminal_screen_reads_the_same_facts_as_the_chat_card(tmp_path):
    import test_prd_writer as w
    env = w.Env(tmp_path, [w.submit()])
    job = env.new()
    f = pj.screen_facts(env.cfg, w.ENV)
    text = pj._screen(job, env.cfg, "first turn")
    assert f"model {f['model']}; turn cap ${f['turn_cap']:.2f}" in text
