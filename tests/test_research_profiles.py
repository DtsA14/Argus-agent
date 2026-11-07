"""SPEC_GATEWAY_PROVIDER PR 2: research profiles (a role per stage), the free OpenRouter profile, and one key file per
provider (router/job.py live, key_files). Models are fakes; keys are test strings in 0600 files."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_research_job as t  # noqa: E402

from models.fake import StrictScriptedChatModel  # noqa: E402
from research import stages as st  # noqa: E402
from router import job as rj  # noqa: E402
from router import research as rr  # noqa: E402
from runner import load_config  # noqa: E402

ROOT = t.ROOT
DS_KEY, OR_KEY = "sk-deepseek-test-0000", "sk-or-v1-test-0000"
WORKED = [t.SEARCH, t.FETCH, t.SUBMIT]


def free_env(tmp_path, planner, worker, checker, **kw):
    env = t.Env(tmp_path, [], **kw)
    env.models = {"free_planner": StrictScriptedChatModel(script=list(planner)),
                  "free_worker": StrictScriptedChatModel(script=list(worker)),
                  "free_checker": StrictScriptedChatModel(script=list(checker))}
    env.deps.models = env.models
    keys = [DS_KEY, OR_KEY]                       # typed in order: deepseek (the web), then openrouter
    env.deps.get_key = lambda: keys.pop(0)
    return env


def key_file(tmp_path, name, content):
    f = tmp_path / "keys" / name
    f.parent.mkdir(exist_ok=True)
    f.write_text(content + "\n")
    f.chmod(0o600)
    return f


# ---- the free profile, end to end ------------------------------------------------------------------------------

def test_a_free_job_runs_each_stage_on_its_own_role(tmp_path):
    env = free_env(tmp_path, [t.PLAN, t.REPORT], WORKED, [t.CHECK])
    job = env.start(profile="free")
    assert job.data["state"] == rr.REPORT_READY and job.data["profile"] == "free"
    assert job.data["stage_roles"] == {"planner": "free_planner", "worker": "free_worker", "synthesis": "free_planner",
                                       "checker": "free_checker"}
    assert all(m.script == [] for m in env.models.values())           # each stage asked its own role's model
    screen = env.confirms[0]
    assert "profile free: planner openrouter:nvidia/nemotron-3-ultra-550b-a55b:free" in screen
    assert "may keep the prompts or train on them" in screen and "keys taken: deepseek" in screen
    assert [k for k, _ in env.spawn.calls] == ["search", "fetch"]     # the web is still DeepSeek
    assert "profile free: planner free_planner" in rj.status("jr", jobs_dir=env.jobs)


def test_the_default_profile_is_deepseek_and_shows_no_free_warning(tmp_path):
    env = t.Env(tmp_path, [t.PLAN, *WORKED, t.REPORT, t.CHECK])
    job = env.start()
    assert job.data["profile"] == "deepseek" and set(job.data["stage_roles"].values()) == {"researcher"}
    assert "may keep the prompts" not in env.confirms[0] and "keys taken" not in env.confirms[0]


def test_a_resumed_job_keeps_the_roles_it_started_with(tmp_path, monkeypatch):
    from research import stages as st
    env = free_env(tmp_path, [t.PLAN, t.REPORT], WORKED, [t.CHECK])
    real, calls = st.run_worker, []

    def interrupted(**kw):
        calls.append(kw["cfg"]["research_job"]["stage_roles"]["worker"])
        if len(calls) == 1:
            raise KeyboardInterrupt
        return real(**kw)
    monkeypatch.setattr(st, "run_worker", interrupted)
    with pytest.raises(KeyboardInterrupt):
        env.start(profile="free")
    env.cfg["research_job"]["profile"] = "deepseek"
    env.cfg["research_job"]["profiles"]["free"]["worker"] = "researcher"      # the config changed since
    keys = [DS_KEY, OR_KEY]
    env.deps.get_key = lambda: keys.pop(0)
    job, _ = rj.resume("jr", cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs)
    assert job.data["state"] == rr.REPORT_READY and calls == ["free_worker", "free_worker"]


# ---- refused before the confirmation ---------------------------------------------------------------------------

def test_an_unknown_profile_creates_no_job(tmp_path):
    env = t.Env(tmp_path, [])
    with pytest.raises(rj.Refused, match="unknown research profile 'nope'"):
        env.start(profile="nope")
    assert env.confirms == [] and not (env.jobs / "jr").exists()


@pytest.mark.parametrize("roles", [{"planner": "free_planner"},
                                   {"planner": "free_planner", "worker": "nobody", "synthesis": "free_planner",
                                    "checker": "free_checker"}])
def test_a_profile_must_name_an_existing_role_for_every_stage(tmp_path, roles):
    env = t.Env(tmp_path, [])
    env.cfg["research_job"]["profiles"]["half"] = roles
    with pytest.raises(rj.Refused, match="must name an existing role for each of"):
        env.start(profile="half")
    assert env.confirms == []


def test_a_free_model_on_a_role_with_repository_tools_creates_no_job(tmp_path):
    env = free_env(tmp_path, [], [], [])
    env.cfg["tools"]["free_worker"] = ["read_file"]
    with pytest.raises(rj.Refused, match="reads repositories"):
        env.start(profile="free")
    assert env.confirms == [] and all(m.calls == [] for m in env.models.values())


def test_a_free_model_on_an_unlisted_role_creates_no_job(tmp_path):
    env = free_env(tmp_path, [], [], [])
    env.cfg["gateway"]["free_roles"] = ["free_planner", "free_worker"]
    with pytest.raises(rj.Refused, match="free_checker"):
        env.start(profile="free")
    assert env.confirms == []


def test_an_unpriced_stage_model_creates_no_job(tmp_path):
    env = t.Env(tmp_path, [])
    del env.cfg["prices"]["openrouter:deepseek/deepseek-v4.1-flash"]
    with pytest.raises(rj.Refused, match="no price"):
        env.start(profile="deepinfra")
    assert env.confirms == []


# ---- keys --------------------------------------------------------------------------------------------------------

def keys_cfg():
    c = t.cfg()
    c["roles"]["or_deepseek"]["model"] = "openrouter:deepseek/deepseek-v4.1-flash"
    return c


def run_live(deps, roles=("or_deepseek",), providers=("deepseek",)):
    seen = {}
    with rj.live(deps, keys_cfg(), list(roles), "screen", providers=list(providers)):
        seen = {v: os.environ.get(v) for v in ("DEEPSEEK_API_KEY", "OPENROUTER_API_KEY")}
    return seen


def deps_with(files, yes=True, typed=None):
    d = rj.Deps(confirm=lambda text: True, get_key=(lambda: typed.pop(0)) if typed else None, isatty=lambda: True,
                clock=lambda: "2026-11-04T00:00:00Z", echo=lambda s: None, key_file=files, assume_yes=yes)
    return d


def test_one_key_file_per_provider_sets_each_key_and_unsets_them_after(tmp_path, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    files = {"deepseek": str(key_file(tmp_path, "ds", DS_KEY)), "openrouter": str(key_file(tmp_path, "or", OR_KEY))}
    assert run_live(deps_with(files)) == {"DEEPSEEK_API_KEY": DS_KEY, "OPENROUTER_API_KEY": OR_KEY}
    assert "DEEPSEEK_API_KEY" not in os.environ and "OPENROUTER_API_KEY" not in os.environ


def test_the_web_provider_key_is_taken_even_when_no_stage_model_uses_it():
    assert [k[0] for k in rj._needs_key(keys_cfg(), ["or_deepseek"], ["deepseek"])] == ["deepseek", "openrouter"]
    assert [k[0] for k in rj._needs_key(keys_cfg(), ["or_deepseek"])] == ["openrouter"]


@pytest.mark.parametrize("which, problem", [
    ("one_path", r"holds one key; this stage needs 2 \(deepseek, openrouter\)"),
    ("missing", r"names \['openrouter'\]; this stage needs a key for \['deepseek', 'openrouter'\]"),
    ("extra", r"names \['anthropic', 'deepseek', 'openrouter'\]"),
])
def test_key_files_must_match_the_providers_that_need_a_key(tmp_path, which, problem):
    ds, orf = str(key_file(tmp_path, "ds", DS_KEY)), str(key_file(tmp_path, "or", OR_KEY))
    files = {"one_path": orf, "missing": {"openrouter": orf},
             "extra": {"deepseek": ds, "openrouter": orf, "anthropic": orf}}[which]
    with pytest.raises(rj.Refused, match=problem):
        run_live(deps_with(files))
    assert "OPENROUTER_API_KEY" not in os.environ


def test_an_openrouter_key_must_look_like_one(tmp_path):
    files = {"deepseek": str(key_file(tmp_path, "ds", DS_KEY)), "openrouter": str(key_file(tmp_path, "or", DS_KEY))}
    with pytest.raises(rj.Refused, match="does not look like one openrouter key"):
        run_live(deps_with(files))


def test_typed_keys_say_which_provider_each_is_for(tmp_path):
    said = []
    d = deps_with(None, yes=False, typed=[DS_KEY, OR_KEY])
    d.echo = said.append
    assert run_live(d) == {"DEEPSEEK_API_KEY": DS_KEY, "OPENROUTER_API_KEY": OR_KEY}
    assert said == ["key for deepseek (DEEPSEEK_API_KEY):", "key for openrouter (OPENROUTER_API_KEY):"]


@pytest.mark.parametrize("given, out", [
    (None, None), (["~/k"], "~/k"), (["deepseek=~/a", "openrouter=~/b"], {"deepseek": "~/a", "openrouter": "~/b"}),
    (["openrouter=~/b"], {"openrouter": "~/b"}),
])
def test_key_file_arguments_are_one_path_or_one_per_provider(given, out):
    assert rj.key_files(given) == out


@pytest.mark.parametrize("given, problem", [
    (["~/a", "~/b"], "give each as PROVIDER=PATH"), (["deepseek=~/a", "~/b"], "give each as PROVIDER=PATH"),
    (["deepseek=~/a", "deepseek=~/b"], "twice"),
])
def test_bad_key_file_arguments_are_refused(given, problem):
    with pytest.raises(rj.Refused, match=problem):
        rj.key_files(given)


def test_the_cli_passes_key_files_per_provider_and_the_profile(tmp_path, monkeypatch, capsys):
    sys.path.insert(0, str(ROOT / "scripts"))
    import argus
    got = {}

    def fake_start(**kw):
        got.update(kw)
        raise rj.Refused("stop here")
    monkeypatch.setattr(rr, "start", fake_start)
    rc = argus.main(["--jobs-dir", str(tmp_path / "jobs"), "research", "--question", t.QUESTION, "--profile", "free",
                     "--key-file", "deepseek=/k/ds", "--key-file", "openrouter=/k/or", "--yes"])
    assert rc == 2 and got["profile"] == "free"
    assert got["deps"].key_file == {"deepseek": "/k/ds", "openrouter": "/k/or"} and got["deps"].assume_yes is True
    rc = argus.main(["--jobs-dir", str(tmp_path / "jobs"), "research", "--question", t.QUESTION,
                     "--key-file", "/k/a", "--key-file", "/k/b"])
    assert rc == 2 and "give each as PROVIDER=PATH" in capsys.readouterr().err


# ---- added from the code and security reviews --------------------------------------------------------------------

@pytest.mark.parametrize("files", ["swapped", "same_file", "one_path_object"])
def test_a_gateway_key_never_goes_to_deepseek(tmp_path, files):
    ds, orf = key_file(tmp_path, "ds", DS_KEY), key_file(tmp_path, "or", OR_KEY)
    given = {"swapped": {"deepseek": str(orf), "openrouter": str(ds)},
             "same_file": {"deepseek": str(orf), "openrouter": str(orf)},
             "one_path_object": orf}[files]
    with pytest.raises(rj.Refused, match="looks like a openrouter key|holds one key|does not look like"):
        run_live(deps_with(given))
    assert "DEEPSEEK_API_KEY" not in os.environ


def test_keys_typed_in_the_wrong_order_are_refused(tmp_path):
    with pytest.raises(rj.Refused, match="the key for deepseek looks like a openrouter key"):
        run_live(deps_with(None, yes=False, typed=[OR_KEY, DS_KEY]))


def test_a_resume_checks_the_stage_roles_again_before_the_confirmation(tmp_path, monkeypatch):
    from research import stages as st
    env = free_env(tmp_path, [t.PLAN], [], [])
    monkeypatch.setattr(st, "run_worker", lambda **kw: (_ for _ in ()).throw(KeyboardInterrupt))
    with pytest.raises(KeyboardInterrupt):
        env.start(profile="free")
    del env.cfg["roles"]["free_checker"]
    confirms = len(env.confirms)
    with pytest.raises(rj.Refused, match="role 'free_checker' is not in the config"):
        rj.resume("jr", cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs)
    assert len(env.confirms) == confirms


def test_preflight_and_screen_use_the_router_overrides(tmp_path):
    env = free_env(tmp_path, [], [], [])
    env.cfg["router"]["overrides"] = {"roles.free_worker.model": "openrouter:x/unlisted"}
    with pytest.raises(rj.Refused, match="x/unlisted"):
        env.start(profile="free")
    assert env.confirms == []


def test_a_stage_whose_limits_do_not_hold_for_its_model_creates_no_job(tmp_path):
    env = free_env(tmp_path, [], [], [])
    env.cfg["prices"]["openrouter:nvidia/nemotron-3.5-lightning:free"]["long_context_above"] = 1000
    with pytest.raises(rj.Refused, match="research checker"):
        env.start(profile="free")
    assert env.confirms == []


def test_without_a_profile_every_stage_uses_the_research_role():
    c = t.cfg()
    del c["research_job"]["profile"]
    assert set(rr.stage_roles(c).values()) == {"researcher"}


def test_the_paid_checker_gets_32k_output_while_the_paid_workers_keep_16k():
    # Rerun 2026-11-04: reasoning.max_tokens was not enforced and e1's reasoning took 15,519 of 16,000 tokens, so the
    # checker stage gets 32,000 on the same model the other stages run with 16,000 (Atha "Ok 32k")
    c = load_config()
    c["research_job"]["stage_roles"] = c["research_job"]["profiles"]["deepinfra"]
    checker = st.with_output_cap(c, "checker")
    assert checker["roles"]["or_deepseek_checker"]["max_output_tokens"] == 32000
    assert checker["roles"]["or_deepseek_checker"]["params"]["extra_body"]["reasoning"] == {"effort": "low"}
    for which in ("planner", "worker", "synthesis"):
        assert st.with_output_cap(c, which)["roles"]["or_deepseek"]["max_output_tokens"] == 16000
    assert checker["roles"]["or_deepseek_checker"]["timeout_s"] >= 32000 / 75     # ~75 tokens/s seen on DeepInfra


def test_a_stage_output_cap_also_reaches_its_fallback_models():
    c = load_config()
    c["research_job"]["checker"]["max_output_tokens_by_model"] = {"openrouter:nvidia/nemotron-3.5-lightning:free": 9000}
    capped = st.with_output_cap(c, "checker")
    assert capped["research_job"]["max_output_tokens_by_model"]["openrouter:nvidia/nemotron-3.5-lightning:free"] == 9000
    assert c["research_job"]["max_output_tokens_by_model"]["openrouter:nvidia/nemotron-3.5-lightning:free"] == 16000


def test_the_paid_checker_asks_for_low_reasoning_effort_alongside_the_gateway_pin():
    # pilots/e1_effort_v0: effort low kept e1's verdicts (30/30) at about half the reasoning; no max_tokens (not enforced)
    from models import gateway
    from models.registry import ModelRef
    c = load_config()
    role = c["roles"]["or_deepseek_checker"]
    extra = gateway.request_params(c, ModelRef.parse(role["model"]), role["params"])["extra_body"]
    assert extra["reasoning"] == {"effort": "low"} and extra["provider"]["require_parameters"] is True
    assert c["roles"]["or_deepseek"].get("params") is None          # the other paid research stages are unchanged
