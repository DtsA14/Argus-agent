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


IMPL_NODES = ("orchestrator", "worker", "synthesize", "evaluator")
IMPL_KINDS = ("fake", "llm")


def parse_impl(items):
    """['worker=llm', ...] -> {'worker': 'llm'}; the last item for a node wins. Raises ConfigError if invalid."""
    out = {}
    for item in items or []:
        node, sep, kind = item.partition("=")
        if not sep or not node or not kind:
            raise ConfigError(f"--impl must look like 'node=kind' (kind 'fake' or 'llm'), got {item!r}")
        if node not in IMPL_NODES:
            raise ConfigError(f"unknown node {node!r}; nodes are {', '.join(IMPL_NODES)}")
        if kind not in IMPL_KINDS:
            raise ConfigError(f"node {node!r}: impl {kind!r} is not valid; use 'fake' or 'llm'")
        out[node] = kind
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


_DEEPSEEK_CLASS = []


def deepseek_class():
    """ChatDeepSeek that sends every earlier assistant reply's reasoning_content back. In thinking mode with tools
    DeepSeek requires it (HTTP 400 otherwise), and langchain_deepseek keeps it on the reply (additional_kwargs) but
    leaves it out of the request. Only what is sent changes: hashes and memo keys never include it."""
    if not _DEEPSEEK_CLASS:
        from langchain_core.messages import AIMessage
        from langchain_deepseek import ChatDeepSeek

        class ArgusChatDeepSeek(ChatDeepSeek):
            def _get_request_payload(self, input_, *, stop=None, **kwargs):
                payload = super()._get_request_payload(input_, stop=stop, **kwargs)
                replies = [m for m in self._convert_input(input_).to_messages() if isinstance(m, AIMessage)]
                sent = [p for p in payload["messages"] if p.get("role") == "assistant"]
                if len(replies) != len(sent):
                    raise ValueError(f"{len(replies)} assistant replies but {len(sent)} in the request")
                for m, p in zip(replies, sent):
                    rc = (m.additional_kwargs or {}).get("reasoning_content")
                    if rc is not None:
                        p["reasoning_content"] = rc
                return payload
        _DEEPSEEK_CLASS.append(ArgusChatDeepSeek)
    return _DEEPSEEK_CLASS[0]


@register_kind("deepseek")
def _deepseek(ref, pcfg, params):
    # DeepSeek turns thinking on by default; params.extra_body {thinking: {type: disabled}} turns it off. With thinking
    # on, deepseek_class() sends the earlier reasoning back, as thinking mode with tools requires.
    return deepseek_class()(
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


def cache_usage(msg):
    """D5: cache tokens of one reply, as langchain_anthropic reports them in input_token_details: reads, 5-minute and
    1-hour writes, and creation (their sum; None when the provider reports no such thing). With a TTL breakdown
    langchain sets the generic cache_creation to 0, so the breakdown wins."""
    um = getattr(msg, "usage_metadata", None) or {}
    d = um.get("input_token_details") or {}
    e5, e1 = d.get("ephemeral_5m_input_tokens"), d.get("ephemeral_1h_input_tokens")
    if e5 is not None or e1 is not None:
        w5, w1 = int(e5 or 0), int(e1 or 0)
    else:
        w5, w1 = (None if d.get("cache_creation") is None else int(d["cache_creation"])), 0
    creation = None if w5 is None else w5 + w1
    return {"read": int(d.get("cache_read") or 0), "write_5m": w5 or 0, "write_1h": w1, "creation": creation}


def price_for(cfg, ref):
    return cfg.get("prices", {}).get(str(ref))


def window_for(cfg, provider):
    return cfg.get("peak_windows", {}).get(provider)


def message_cost(cfg, ref, msg, now=None):
    tin, tout, cached = usage_from_message(msg)
    c = cache_usage(msg)
    return cost_usd(
        price_for(cfg, ref),
        input_tokens=tin,
        output_tokens=tout,
        cache_read_tokens=cached,
        cache_write_tokens=c["write_5m"],
        cache_write_1h_tokens=c["write_1h"],
        window=window_for(cfg, ref.provider),
        now=now,
    )
