"""Config-driven LLM provider layer: providers and roles live in config.yaml, not in code."""
import copy
import os
from dataclasses import dataclass

from .pricing import cost_usd


class ConfigError(Exception):
    pass


class MissingApiKey(Exception):
    pass


@dataclass(frozen=True)
class ModelRef:
    provider: str
    model: str

    @classmethod
    def parse(cls, text):
        provider, _, model = str(text).partition(":")
        if not provider or not model:
            raise ConfigError(f"model must look like 'provider:model-id', got {text!r}")
        return cls(provider, model)

    def __str__(self):
        return f"{self.provider}:{self.model}"


# ---- swapping models ------------------------------------------------------

def parse_overrides(items):
    """['worker=openai:gpt-x', ...] -> {'worker': 'openai:gpt-x'}"""
    out = {}
    for item in items or []:
        role, sep, ref = item.partition("=")
        if not sep or not role:
            raise ConfigError(f"override must look like 'role=provider:model', got {item!r}")
        out[role] = str(ModelRef.parse(ref))
    return out


def apply_overrides(cfg, overrides):
    """Return a copy of cfg with role -> model replaced; the original is untouched."""
    out = copy.deepcopy(cfg)
    for role, ref_text in overrides.items():
        if role not in out.get("roles", {}):
            raise ConfigError(f"unknown role {role!r}; roles are {sorted(out.get('roles', {}))}")
        ref = ModelRef.parse(ref_text)
        if ref.provider not in out.get("providers", {}):
            raise ConfigError(f"unknown provider {ref.provider!r}; providers are {sorted(out['providers'])}")
        out["roles"][role]["model"] = str(ref)
    return out


def role_warnings(cfg):
    roles = cfg.get("roles", {})
    if "worker" not in roles or "evaluator" not in roles:
        return []
    worker = ModelRef.parse(roles["worker"]["model"])
    evaluator = ModelRef.parse(roles["evaluator"]["model"])
    warnings = []
    if worker.provider == evaluator.provider:
        warnings.append(
            f"evaluator and worker both use provider '{worker.provider}'; "
            "a different provider reduces self-grading bias"
        )
    return warnings


# ---- building chat models -------------------------------------------------

BUILDERS = {}


def register_kind(kind):
    """Register a builder for a new provider kind: fn(ref, provider_cfg, params) -> chat model."""
    def deco(fn):
        BUILDERS[kind] = fn
        return fn
    return deco


def _api_key(ref, pcfg):
    env = pcfg.get("api_key_env")
    key = os.environ.get(env) if env else None
    if not key:
        raise MissingApiKey(f"{ref.provider}: environment variable {env} is not set")
    return key


@register_kind("anthropic")
def _anthropic(ref, pcfg, params):
    from langchain_anthropic import ChatAnthropic
    kw = {"model": ref.model, "api_key": _api_key(ref, pcfg), **params}
    if pcfg.get("base_url"):
        kw["base_url"] = pcfg["base_url"]
    return ChatAnthropic(**kw)


@register_kind("openai")
def _openai(ref, pcfg, params):
    from langchain_openai import ChatOpenAI
    kw = {"model": ref.model, "api_key": _api_key(ref, pcfg), **params}
    if pcfg.get("base_url"):
        kw["base_url"] = pcfg["base_url"]
    return ChatOpenAI(**kw)


@register_kind("deepseek")
def _deepseek(ref, pcfg, params):
    from langchain_deepseek import ChatDeepSeek
    # DeepSeek turns thinking on by default; tune it with params.extra_body if needed.
    return ChatDeepSeek(
        model=ref.model,
        api_key=_api_key(ref, pcfg),
        api_base=pcfg.get("base_url", "https://api.deepseek.com"),
        **params,
    )


@register_kind("openai_compatible")
def _openai_compatible(ref, pcfg, params):
    from langchain_openai import ChatOpenAI
    if not pcfg.get("base_url"):
        raise ConfigError(f"{ref.provider}: kind openai_compatible needs base_url")
    return ChatOpenAI(model=ref.model, api_key=_api_key(ref, pcfg), base_url=pcfg["base_url"], **params)


@register_kind("fake")
def _fake(ref, pcfg, params):
    """Scripted model for tests and offline demos: no network, no key. The script is a JSON file whose
    path is in the environment variable named by pcfg['script_env'] (default ARGUS_FAKE_SCRIPT)."""
    from models.fake import FileScriptedChatModel
    env = pcfg.get("script_env", "ARGUS_FAKE_SCRIPT")
    path = os.environ.get(env)
    if not path:
        raise MissingApiKey(f"{ref.provider}: set {env} to a JSON script file")
    return FileScriptedChatModel(path=path)


def build_chat_model(cfg, role):
    if role not in cfg.get("roles", {}):
        raise ConfigError(f"unknown role {role!r}")
    rcfg = cfg["roles"][role]
    ref = ModelRef.parse(rcfg["model"])
    pcfg = cfg.get("providers", {}).get(ref.provider)
    if pcfg is None:
        raise ConfigError(f"role {role!r} uses unknown provider {ref.provider!r}")
    builder = BUILDERS.get(pcfg.get("kind"))
    if builder is None:
        raise ConfigError(f"provider {ref.provider!r} has unknown kind {pcfg.get('kind')!r}; known: {sorted(BUILDERS)}")
    params = dict(rcfg.get("params", {}))
    # The provider SDKs retry on their own by default (Anthropic: 2, OpenAI client: 2). Those hidden
    # attempts would be billed outside our ledger, so they are switched off; harness/llm.py retries instead.
    params["max_retries"] = 0
    if "timeout_s" in rcfg:
        params.setdefault("timeout", rcfg["timeout_s"])
    return builder(ref, pcfg, params)


def list_models(cfg, provider):
    """Ask the provider which model ids it offers (needs its API key)."""
    pcfg = cfg["providers"][provider]
    key = _api_key(ModelRef(provider, ""), pcfg)
    if pcfg["kind"] == "anthropic":
        import anthropic
        kw = {"api_key": key}
        if pcfg.get("base_url"):
            kw["base_url"] = pcfg["base_url"]
        client = anthropic.Anthropic(**kw)
    else:
        import openai
        client = openai.OpenAI(api_key=key, base_url=pcfg.get("base_url"))
    return sorted(m.id for m in client.models.list())


# ---- usage and cost -------------------------------------------------------

def usage_from_message(msg):
    """(input_tokens, output_tokens, cache_read_tokens) from a LangChain AIMessage."""
    um = getattr(msg, "usage_metadata", None) or {}
    details = um.get("input_token_details") or {}
    return um.get("input_tokens", 0), um.get("output_tokens", 0), details.get("cache_read", 0)


def price_for(cfg, ref):
    return cfg.get("prices", {}).get(str(ref))


def window_for(cfg, provider):
    return cfg.get("peak_windows", {}).get(provider)


def message_cost(cfg, ref, msg, now=None):
    tin, tout, cached = usage_from_message(msg)
    return cost_usd(
        price_for(cfg, ref),
        input_tokens=tin,
        output_tokens=tout,
        cache_read_tokens=cached,
        window=window_for(cfg, ref.provider),
        now=now,
    )
