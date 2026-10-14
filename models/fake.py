"""Scripted chat model for tests: no network, no cost, fully deterministic.

Each invoke() consumes the next scripted item:
  - an AIMessage   -> returned (may carry tool_calls and usage_metadata)
  - an Exception   -> raised (to simulate rate limits, timeouts, bad requests)
Every call's messages and kwargs (e.g. max_tokens) are recorded in .calls for assertions.
"""
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field


class ScriptedChatModel(BaseChatModel):
    script: list = Field(default_factory=list)
    calls: list = Field(default_factory=list)
    bound_tools: list = Field(default_factory=list)
    tool_choice: Any = None
    max_retries: int = 0
    timeout: float | None = None

    @property
    def _llm_type(self) -> str:
        return "scripted-fake"

    def bind_tools(self, tools, tool_choice=None, **kwargs: Any):
        self.bound_tools = list(tools)
        self.tool_choice = tool_choice
        return self

    def _next(self):
        if not self.script:
            raise AssertionError("ScriptedChatModel: script exhausted (more calls than expected)")
        return self.script.pop(0)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.calls.append({"messages": list(messages), "kwargs": dict(kwargs), "tool_choice": self.tool_choice})
        item = self._next()
        if isinstance(item, BaseException):
            raise item
        if not isinstance(item, AIMessage):
            raise TypeError(f"script items must be AIMessage or Exception, got {type(item).__name__}")
        return ChatResult(generations=[ChatGeneration(message=item)])


def reply(text="ok", *, input_tokens=100, output_tokens=20, cache_read=0, tool_calls=None, usage=True):
    """Build a scripted AIMessage with provider-style usage metadata."""
    kw = {"content": text}
    if tool_calls:
        kw["tool_calls"] = tool_calls
    if usage:
        kw["usage_metadata"] = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "input_token_details": {"cache_read": cache_read},
        }
    return AIMessage(**kw)


def item_from_json(d):
    """JSON script item -> AIMessage or exception. {"error_status": 429} raises; otherwise a reply."""
    if "error_status" in d:
        return FakeHTTPError(d["error_status"], d.get("message", ""), d.get("retry_after"))
    usage = d.get("usage", {"input_tokens": 100, "output_tokens": 20})
    return reply(d.get("content", ""), input_tokens=usage.get("input_tokens", 0),
                 output_tokens=usage.get("output_tokens", 0), cache_read=usage.get("cache_read", 0),
                 tool_calls=d.get("tool_calls"), usage=bool(usage))


class FileScriptedChatModel(ScriptedChatModel):
    """Script read from a JSON file, with the read position persisted next to it, so a script
    continues correctly across processes (crash, then --resume). Used by provider kind 'fake'."""
    path: str = ""

    def _next(self):
        import json
        from pathlib import Path
        items = json.loads(Path(self.path).read_text(encoding="utf-8"))
        pos_file = Path(self.path + ".pos")
        pos = int(pos_file.read_text()) if pos_file.exists() else 0
        if pos >= len(items):
            raise AssertionError(f"fake script {self.path} exhausted after {pos} calls")
        pos_file.write_text(str(pos + 1))
        return item_from_json(items[pos])


class FakeHTTPError(Exception):
    """Mimics SDK errors: carries status_code and optional response headers."""

    def __init__(self, status_code, message="", retry_after=None):
        super().__init__(message or f"HTTP {status_code}")
        self.status_code = status_code
        headers = {"retry-after": str(retry_after)} if retry_after is not None else {}
        self.response = type("Resp", (), {"headers": headers, "status_code": status_code})()
