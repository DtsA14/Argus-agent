"""Live check of every configured role: API key, model id, plain chat, tool calling.

  python scripts/smoke_models.py                      # test each role's model (skips providers without a key)
  python scripts/smoke_models.py --list               # list model ids each provider offers
  python scripts/smoke_models.py --list --grep gpt    # ...filtered
  python scripts/smoke_models.py --model worker=deepseek:deepseek-flash
"""
import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_core.tools import tool

from models.registry import (
    ConfigError, MissingApiKey, ModelRef, apply_overrides, build_chat_model,
    list_models, message_cost, parse_overrides, usage_from_message,
)
from runner import load_config


@tool
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


def fmt_cost(cost):
    return f"${cost:.6f}" if cost is not None else "cost n/a"


def smoke_role(cfg, role):
    ref = ModelRef.parse(cfg["roles"][role]["model"])
    label = f"{role:<13} {str(ref):<34}"
    try:
        model = build_chat_model(cfg, role)
    except MissingApiKey as e:
        print(f"{label} SKIP ({e})")
        return None

    ok = True
    t0 = time.monotonic()
    try:
        msg = model.invoke("Reply with exactly: OK")
        tin, tout, _ = usage_from_message(msg)
        chat = f"chat OK {time.monotonic() - t0:.1f}s in={tin} out={tout} {fmt_cost(message_cost(cfg, ref, msg))}"
    except Exception as e:  # report any provider error, never crash the whole run
        chat = f"chat FAIL {type(e).__name__}: {str(e)[:160]}"
        ok = False

    try:
        msg = model.bind_tools([add]).invoke("What is 17 + 25? You must call the add tool.")
        calls = getattr(msg, "tool_calls", None) or []
        good = bool(calls) and calls[0]["name"] == "add"
        tools = "tools OK" if good else "tools FAIL (no tool call returned)"
        ok = ok and good
    except Exception as e:
        tools = f"tools FAIL {type(e).__name__}: {str(e)[:160]}"
        ok = False

    print(f"{label} {chat} | {tools}")
    return ok


def run_list(cfg, grep):
    for name, pcfg in cfg["providers"].items():
        env = pcfg.get("api_key_env")
        if not os.environ.get(env or ""):
            print(f"{name}: SKIP ({env} not set)")
            continue
        try:
            ids = list_models(cfg, name)
        except Exception as e:
            print(f"{name}: FAIL {type(e).__name__}: {str(e)[:160]}")
            continue
        shown = [i for i in ids if grep.lower() in i.lower()] if grep else ids
        suffix = f" ({len(shown)} match '{grep}')" if grep else ""
        print(f"{name}: {len(ids)} models{suffix}")
        for i in shown[:60]:
            print(f"    {i}")
        for role, rc in cfg["roles"].items():
            ref = ModelRef.parse(rc["model"])
            if ref.provider == name and ref.model not in ids:
                print(f"    !! role '{role}' uses '{ref.model}', not found in this provider's list "
                      "(may still work if it is an alias)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--grep", default="")
    ap.add_argument("--role", action="append", help="only test this role (repeatable)")
    ap.add_argument("--model", action="append", help="override, e.g. worker=deepseek:deepseek-flash")
    a = ap.parse_args()

    try:
        cfg = apply_overrides(load_config(), parse_overrides(a.model))
    except ConfigError as e:
        sys.exit(f"config error: {e}")

    if a.list:
        run_list(cfg, a.grep)
        return

    results = [smoke_role(cfg, role) for role in (a.role or cfg["roles"])]
    tested = [r for r in results if r is not None]
    if not tested:
        print("\nNothing was tested: set ANTHROPIC_API_KEY / OPENAI_API_KEY / DEEPSEEK_API_KEY first.")
        sys.exit(2)
    print(f"\n{sum(tested)}/{len(tested)} roles passed, {results.count(None)} skipped (no API key)")
    sys.exit(0 if all(tested) else 1)


if __name__ == "__main__":
    main()
