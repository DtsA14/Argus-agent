"""The gateway provider kind (docs/reviews/SPEC_GATEWAY_PROVIDER.md): one key for many models through an
OpenAI-compatible gateway. Vendor openrouter only (Vercel later, §9).

  - Only models listed in `gateway_models` may be used; each names the upstream providers it is pinned to.
  - Every request carries the pin: order = only = upstream, no fallbacks, no `models` list, no sort (§3). A reply that
    says it was served by another provider is a pin violation: recorded and charged, then the call fails.
  - A free model (`free: true`) is used only by a role in `gateway.free_roles`, and never by a role with a tool that
    reads a repo (§5.1; per-repo opening comes with scripts/check_secrets.py in a later PR).
  - The gateway's reported cost is kept; LLMCaller charges the larger of it and its own count (§4).

Nothing here sends anything: it checks the config and shapes the request, and reads what the reply reported.
"""
import math

from .registry import ConfigError

VENDORS = ("openrouter",)
REPO_TOOLS = {"list_files", "search_files", "read_file", "write_file", "run_validation", "read_docs"}


def is_gateway(cfg, ref):
    return ((cfg.get("providers") or {}).get(ref.provider) or {}).get("kind") == "gateway"


def entry(cfg, ref):
    """The model's gateway_models entry, checked; ConfigError when it is missing or malformed."""
    pcfg = cfg["providers"][ref.provider]
    if pcfg.get("vendor") not in VENDORS:
        raise ConfigError(f"provider {ref.provider!r}: gateway vendor {pcfg.get('vendor')!r} is not supported; "
                          f"supported: {list(VENDORS)}")
    e = (cfg.get("gateway_models") or {}).get(str(ref))
    if e is None:
        raise ConfigError(f"{ref} is not in gateway_models: only listed models, pinned to their upstream providers, "
                          "may be used through a gateway")
    up = e.get("upstream")
    if not (isinstance(up, list) and up and all(isinstance(u, str) and u.strip() for u in up)):
        raise ConfigError(f"gateway_models[{str(ref)!r}].upstream must be a non-empty list of provider slugs")
    if not isinstance(e.get("free", False), bool):
        raise ConfigError(f"gateway_models[{str(ref)!r}].free must be true or false")
    return {"upstream": [u.strip() for u in up], "free": e.get("free", False)}


def check_use(cfg, role, ref):
    """Refuse, before anything is sent, a gateway model this role may not use (§5, §5.1)."""
    if not is_gateway(cfg, ref):
        return
    e = entry(cfg, ref)
    if not e["free"]:
        return
    free_roles = (cfg.get("gateway") or {}).get("free_roles") or []
    if role not in free_roles:
        raise ConfigError(f"role {role!r} may not use the free model {ref}: prompts to free models may be kept or used "
                          "for training by their provider; list the role in gateway.free_roles to allow it")
    reads = sorted(REPO_TOOLS & set((cfg.get("tools") or {}).get(role) or []))
    if reads:
        raise ConfigError(f"role {role!r} reads repositories ({', '.join(reads)}) and may not use the free model {ref}: "
                          "what it reads would go to a provider that may keep it")


def request_params(cfg, ref, params):
    """The role's params with the pin added to extra_body (OpenRouter's `provider` object)."""
    e = entry(cfg, ref)
    extra = dict(params.get("extra_body") or {})
    for k in ("provider", "models", "route", "sort"):
        if k in extra:
            raise ConfigError(f"{ref}: extra_body.{k} is set by the gateway pin, not by role params")
    extra["provider"] = {"order": e["upstream"], "only": e["upstream"], "allow_fallbacks": False,
                         "require_parameters": True, "data_collection": "allow" if e["free"] else "deny"}
    return {**params, "extra_body": extra}


def _slug(s):
    return "".join(ch for ch in str(s).lower() if ch.isalnum())


def served_ok(cfg, ref, served):
    """False only when the reply names a provider outside the pin (None: the reply did not say)."""
    if served is None:
        return True
    return _slug(served) in {_slug(u) for u in entry(cfg, ref)["upstream"]}


def reported(msg):
    """(cost in USD or None, serving provider or None) as the gateway reported them on the reply."""
    meta = getattr(msg, "response_metadata", None) or {}
    cost = meta.get("gateway_cost")
    if isinstance(cost, bool) or not isinstance(cost, (int, float)) or not math.isfinite(cost) or cost < 0:
        cost = None
    served = meta.get("gateway_provider")
    return cost, (served if isinstance(served, str) and served.strip() else None)


_CLASS = []


def chat_class():
    """ChatOpenAI that keeps what the gateway adds to a reply (usage.cost, provider) in response_metadata."""
    if not _CLASS:
        from langchain_openai import ChatOpenAI

        class ArgusChatGateway(ChatOpenAI):
            def _create_chat_result(self, response, generation_info=None):
                result = super()._create_chat_result(response, generation_info)
                d = response if isinstance(response, dict) else response.model_dump(warnings=False)
                usage = d.get("usage") or {}
                for g in result.generations:
                    g.message.response_metadata["gateway_cost"] = usage.get("cost")
                    g.message.response_metadata["gateway_provider"] = d.get("provider")
                return result
        _CLASS.append(ArgusChatGateway)
    return _CLASS[0]


def build(cfg, role, ref, pcfg, params, api_key):
    if not pcfg.get("base_url"):
        raise ConfigError(f"{ref.provider}: kind gateway needs base_url")
    check_use(cfg, role, ref)
    return chat_class()(model=ref.model, api_key=api_key, base_url=pcfg["base_url"], **request_params(cfg, ref, params))

