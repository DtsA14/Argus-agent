"""DeepSeek thinking mode with tools (docs: api-docs.deepseek.com/guides/thinking_mode): every earlier assistant
reply's reasoning_content must be sent back, or the API answers HTTP 400. langchain_deepseek keeps it on the reply but
leaves it out of the request; Argus adds it to what is sent and keeps it in the step memo, so a resumed loop sends it
too. No network: the request payload is built, never sent."""
import json
import sys
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from harness.steps import message_from_json, message_to_json
from models.registry import build_chat_model
from runner import load_config

sys.path.insert(0, str(Path(__file__).resolve().parent))


def thinking_cfg():
    c = load_config()
    c["roles"]["drafter"]["params"] = {"extra_body": {"thinking": {"type": "enabled"}}}
    return c


def test_every_earlier_reasoning_is_sent_back_and_only_where_there_was_one(monkeypatch):
    pytest.importorskip("langchain_deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    model = build_chat_model(thinking_cfg(), "drafter")
    a1 = AIMessage(content="", additional_kwargs={"reasoning_content": "first thought"},
                   tool_calls=[{"name": "ReadFile", "args": {"path": "a"}, "id": "c1"}])
    a2 = AIMessage(content="ok", tool_calls=[{"name": "ReadFile", "args": {"path": "b"}, "id": "c2"}])
    a3 = AIMessage(content="", additional_kwargs={"reasoning_content": "third"},
                   tool_calls=[{"name": "ReadFile", "args": {"path": "c"}, "id": "c3"}])
    msgs = [HumanMessage("task"), a1, ToolMessage("A", tool_call_id="c1"), a2, ToolMessage("B", tool_call_id="c2"),
            a3, ToolMessage("C", tool_call_id="c3")]
    sent = [p for p in model._get_request_payload(msgs)["messages"] if p["role"] == "assistant"]
    assert [p.get("reasoning_content") for p in sent] == ["first thought", None, "third"]
    assert "reasoning_content" not in sent[1]
    assert model.extra_body == {"thinking": {"type": "enabled"}}


def test_the_step_memo_keeps_the_reasoning_and_old_entries_read_as_before():
    msg = AIMessage(content="", additional_kwargs={"reasoning_content": "why"},
                    tool_calls=[{"name": "ReadFile", "args": {"path": "a"}, "id": "c1"}])
    d = message_to_json(msg)
    assert d["reasoning_content"] == "why"
    back = message_from_json(json.loads(json.dumps(d)))
    assert back.additional_kwargs == {"reasoning_content": "why"} and back.tool_calls[0]["id"] == "c1"
    plain = message_to_json(AIMessage(content="x"))
    assert "reasoning_content" not in plain and message_from_json(plain).additional_kwargs == {}


@pytest.mark.skipif(sys.platform == "win32", reason="the path jail needs openat; the VM runs these")
def test_a_resumed_drafter_sends_back_the_reasoning_of_replayed_steps(tmp_path):
    """A model that rejects any request whose earlier tool-calling replies lack their reasoning (as DeepSeek does)
    works across a stop and a resume: the replayed step comes from the memo with its reasoning."""
    import test_drafter as td
    from codetask import drafter as dt
    from models.fake import CallableChatModel, reply

    def with_reasoning(msg, text):
        msg.additional_kwargs["reasoning_content"] = text
        return msg

    def strict(script):
        state = {"n": 0}

        def respond(messages):
            for m in messages:
                if isinstance(m, AIMessage) and m.tool_calls and not (m.additional_kwargs or {}).get("reasoning_content"):
                    return RuntimeError("HTTP 400: reasoning_content must be passed back")
            item = script[state["n"]]
            state["n"] += 1
            return item() if callable(item) else item
        return CallableChatModel(respond=respond)

    def stop():
        raise KeyboardInterrupt
    root = td.make_root(tmp_path)
    c = td.cfg()
    read = with_reasoning(td.call("ReadFile", {"path": "src/shop.py"}, "r1"), "look at the code first")
    first = strict([read, stop])
    with pytest.raises(KeyboardInterrupt):
        dt.run_drafter(run_id="d", runs_dir=tmp_path / "runs", cfg=c, intake_name="shop", issue=td.ISSUE, max_usd=0.4,
                       models={"drafter": first}, validate=td.fake_validate, preflight=lambda: (True, "ok"),
                       env_preflight=lambda name: (True, "ok"), root=root, red=td.fake_red)
    second = strict([with_reasoning(td.call("SubmitDraft", td.ARGS, "s1"), "now submit")])
    r = dt.run_drafter(run_id="d", runs_dir=tmp_path / "runs", cfg=c, resume=True, models={"drafter": second},
                       validate=td.fake_validate, preflight=lambda: (True, "ok"), env_preflight=lambda name: (True, "ok"),
                       root=root, red=td.fake_red)
    assert r["status"] == dt.DRAFTED and len(second.calls) == 1
    replayed = [m for m in second.calls[0]["messages"] if isinstance(m, AIMessage)]
    assert replayed[0].additional_kwargs["reasoning_content"] == "look at the code first"
