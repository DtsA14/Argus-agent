"""Who started a human message of a PRD conversation, as far as the record knows (SPEC_CHAT_UI2).

The record says only this: the created log entry carries `via: ui` when the job was started with `--via ui` (the chat always
does; a terminal can pass it too). Chat has no reply action, so every later human message was typed in a terminal, by the
human or by a Claude session; the record cannot tell which. Nothing here claims more.
"""

CHAT, TERMINAL = "chat", "terminal"
LABELS = {CHAT: "started in chat (recorded via ui)",
          TERMINAL: "typed in the terminal (the human or a Claude session; not recorded which)"}
LABELS_ID = {CHAT: "dimulai lewat chat (tercatat via ui)",
             TERMINAL: "dari terminal (manusia atau sesi Claude, tidak tercatat)"}


def via_ui(data):
    return any(isinstance(e, dict) and e.get("what") == "created" and e.get("via") == "ui" for e in data.get("log") or [])


def human_messages(data, stop_turn=None):
    """[(text, by)] for every human message, by the position in `conversation`: only the first message of the conversation can be
    "chat", and only when it is the first entry of the conversation. stop_turn: stop at the writer's reply of that turn."""
    out, ui = [], via_ui(data)
    for pos, m in enumerate(data.get("conversation") or []):
        if not isinstance(m, dict):
            continue
        if stop_turn is not None and m.get("from") == "writer" and m.get("stage") == stop_turn:
            break
        if m.get("from") == "human" and isinstance(m.get("text"), str):
            out.append((m["text"], CHAT if (pos == 0 and ui) else TERMINAL))
    return out


import re
import unicodedata

REF_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
REF_COMMIT = re.compile(r"[0-9a-f]{40}")
UNREADABLE = "unreadable"


def ref_facts(data):
    """The other repositories the writer read (SPEC_CHAT_UI2 F12): None when the job has none, [{"name", "commit12"}] when they are
    readable, UNREADABLE when the key is there but is not the shape the job freezes (never an error, never silently nothing)."""
    if "refs" not in data or data["refs"] in (None, []):
        return None
    from router import prd_refs            # a late import: prd_refs pulls the writer, and this module is read by the card builders
    refs = data["refs"]
    if not prd_refs.valid(refs) or not refs:
        return UNREADABLE
    out = []
    for r in refs:
        if not (REF_NAME.fullmatch(r["name"]) and REF_COMMIT.fullmatch(r["commit"])):
            return UNREADABLE
        out.append({"name": r["name"], "commit12": r["commit"][:12]})
    return out


def excerpt(text, limit):
    """(text, cut): format characters (bidi and the like) dropped, then cut by code points, never inside a surrogate pair."""
    clean = "".join(ch for ch in text if unicodedata.category(ch) != "Cf")
    return (clean[:limit], True) if len(clean) > limit else (clean, False)
