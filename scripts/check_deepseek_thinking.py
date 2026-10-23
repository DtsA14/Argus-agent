"""Check, with one real request pair, that DeepSeek accepts Argus's thinking-mode tool loop: a first call with a tool,
a tool result, and a second call that carries the first reply's reasoning_content back (DeepSeek answers HTTP 400
when it is missing). Every call goes through LLMCaller, with a reservation of $0.02 and a ledger in a temporary
directory. Costs a fraction of a cent.

  python scripts/check_deepseek_thinking.py          # asks for the DeepSeek key (not shown); needs a terminal

Exit codes: 0 accepted, 1 refused by the API or no reasoning came back, 2 refused before sending.
"""
import getpass
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from harness.errors import LLMCallFailed  # noqa: E402
from harness.events import EventLog  # noqa: E402
from harness.llm import LLMCaller, Reservation, reconcile_ledger  # noqa: E402
from runner import load_config  # noqa: E402


class GetNumber(BaseModel):
    """Return the secret number."""
    name: str = Field(description="Which number: 'secret'")


def main():
    if not sys.stdin.isatty():
        print("refused: run it in a terminal; the key is typed, never passed", file=sys.stderr)
        return 2
    key = getpass.getpass("Type or paste the DeepSeek API key, then Enter (not shown): ").strip()
    if not key or any(c.isspace() for c in key):
        print("refused: the key is empty or has whitespace", file=sys.stderr)
        return 2
    cfg = load_config()
    role = "drafter"
    cfg["roles"][role] = {**cfg["roles"][role], "model": "deepseek:deepseek-flash", "max_output_tokens": 2048,
                          "params": {"extra_body": {"thinking": {"type": "enabled"}}, "reasoning_effort": "low"}}
    cfg["budget"]["max_usd"] = 0.02
    os.environ["DEEPSEEK_API_KEY"] = key
    try:
        with tempfile.TemporaryDirectory() as d:
            log = EventLog(Path(d) / "events.jsonl")
            caller = LLMCaller(cfg, role, log)
            res = Reservation(tokens=20000, usd=0.02)
            meta = {"node": "check", "task": "deepseek_thinking", "iteration": 0}
            msgs = [SystemMessage("Use the tool to get the secret number, then answer with it."),
                    HumanMessage("What is the secret number?")]
            first = caller.call(msgs, res, tools=[GetNumber], meta={**meta, "step": 0})
            reasoning = (first.additional_kwargs or {}).get("reasoning_content")
            calls = first.tool_calls or []
            print(f"first reply: {len(calls)} tool call(s); reasoning_content: {len(reasoning or '')} characters")
            if not calls or not reasoning:
                print("FAIL: thinking mode gave no tool call or no reasoning to send back")
                return 1
            msgs += [first, ToolMessage("42", tool_call_id=calls[0]["id"])]
            second = caller.call(msgs, res, tools=[GetNumber], meta={**meta, "step": 1})
            _, totals = reconcile_ledger(log.read())
            print(f"second reply accepted: {str(second.content)[:80]!r}; cost ${totals['usd']:.6f}")
            print("OK: DeepSeek accepted the reasoning sent back")
            return 0
    except LLMCallFailed as e:
        print(f"FAIL: the API refused: {str(e)[:300]}")
        return 1
    finally:
        os.environ.pop("DEEPSEEK_API_KEY", None)


if __name__ == "__main__":
    sys.exit(main())
