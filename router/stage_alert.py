"""A notification when the staging monitor keeps failing (Atha 2026-10-30, after the live release was down for 16 runs
unnoticed): one ntfy message after FAILS_IN_A_ROW failed runs in a row, one when a run passes again; never one per run.

A busy run (ok null: another refresh held the data lock, or the live release changed during the smoke test) is not a
failure (Atha) and does not break a run of failures; but BUSY_IN_A_ROW busy runs in a row (an hour: a lock that stays
held, so nothing is smoke-tested) are reported as stuck. A monitor run that crashed is recorded as failed by the CLI
before this runs. Not covered: runs that never start (timer, venv or VM down).

The message names the release(s), which checks failed and the harness's reasons; an answer of the app is reduced to its
status ("answered 500"), so no API data leaves the VM. The ntfy topic is read from a 0600 regular file outside the
repository (never an argument, never next to the API key): a topic name (ntfy.sh) or https://<server>/<topic> for a
server of SERVERS; without a valid one nothing is sent and the run says so.
State: <staging>/alert.json (0600), under its own lock. A FAIL that could not be sent is tried again at the next run; a
recovery that could not be sent is kept and sent at a later run, and never blocks the next FAIL.
"""
import fcntl
import json
import os
import re
import stat
import time
import urllib.request
from pathlib import Path

from .stage_data import _records

FAILS_IN_A_ROW = 3                                      # 15-minute runs: about 30-45 minutes after it broke
BUSY_IN_A_ROW = 4                                       # an hour without a smoke test
NTFY = "https://ntfy.sh"
# ntfy servers a topic file may name (https://<server>/<topic>; a bare topic is ntfy.sh's). ntfy-me.com: the iOS app
# Atha's phone gets pushes from (2026-10-30: the official app showed messages only on refresh).
SERVERS = ("ntfy.sh", "ntfy-me.com")
TOPIC_FILE = Path.home() / ".ntfy" / "argus_topic"   # not next to the API key file
TOPIC = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
SEND_TIMEOUT_S = 10
STATUS_DETAIL = re.compile(r"^(\d{3}) ")                # "<status> <body or sha>": the app's answer, never sent


def streak(records):
    """(failed runs since the last pass, busy runs at the end, the last failed or passed record). Busy runs (ok not a
    bool) neither count as failures nor end a run of them."""
    decided = [r for r in records if isinstance(r.get("ok"), bool)]
    failed = 0
    for r in reversed(decided):
        if r["ok"]:
            break
        failed += 1
    busy = 0
    for r in reversed(records):
        if isinstance(r.get("ok"), bool):
            break
        busy += 1
    return failed, busy, (decided[-1] if decided else None)


def _why(detail):
    m = STATUS_DETAIL.match(str(detail))
    return f"answered {m.group(1)}" if m else str(detail)[:160]


def _failed(smoke):
    return [f"{check}: {_why(detail)}" for check, ok, detail in smoke or [] if not ok]


def describe(rec):
    """The text of a failure message: release(s), failed checks and reasons, without the app's data."""
    lines = [f"release {rec.get('release') or 'nothing live'}"]
    refresh = rec.get("refresh") or {}
    if refresh.get("ok") is False:
        kind = str(refresh.get("why") or "").split(":", 1)[0]
        lines.append(f"refresh failed ({kind[:40] or 'unknown'})")
    lines += _failed(rec.get("smoke"))
    if rec.get("why") and not rec.get("smoke"):
        lines.append(str(rec["why"])[:160])
    viewer = rec.get("viewer")
    if isinstance(viewer, dict) and viewer.get("ok") is False:
        lines.append(f"viewer {viewer.get('release') or '(state unreadable)'}")
        lines += _failed(viewer.get("smoke"))
        if viewer.get("why") and not viewer.get("smoke"):
            lines.append(str(viewer["why"])[:160])
    return "\n".join(lines)


def topic_url(topic_file):
    """The ntfy URL from a private regular topic file (opened without following a link), or (None, why)."""
    p = Path(topic_file)
    try:
        fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as e:
        return None, f"no readable topic file {p} ({type(e).__name__})"
    with os.fdopen(fd, "rb") as f:
        st = os.fstat(f.fileno())
        if not stat.S_ISREG(st.st_mode):
            return None, f"{p} is not a regular file"
        if st.st_mode & 0o077:
            return None, f"{p} can be read by others (chmod 600 it)"
        topic = f.read(300).decode("utf-8", "replace").strip()
    server = "ntfy.sh"
    m = re.fullmatch(r"https://([a-z0-9.-]+)/([^/?#\s]+)", topic)
    if m:
        server, topic = m.groups()
        if server not in SERVERS:
            return None, f"{p} names server {server!r}, not one of {', '.join(SERVERS)}"
    if not TOPIC.match(topic):
        return None, f"{p} does not hold a topic name ([A-Za-z0-9_-], 16-64), bare or as https://<server>/<topic>"
    return f"https://{server}/{topic}", None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):               # a redirect is an error, never a POST re-sent elsewhere
        return None


def ntfy(url, title, text, *, urgent):
    """POST the message to ntfy: the message, its title, priority and tags; nothing else."""
    req = urllib.request.Request(url, data=text.encode("utf-8"), method="POST", headers={
        "Title": title, "Priority": "high" if urgent else "default",
        "Tags": "warning" if urgent else "white_check_mark"})
    with urllib.request.build_opener(_NoRedirect).open(req, timeout=SEND_TIMEOUT_S) as r:
        if r.status != 200:
            raise OSError(f"ntfy answered {r.status}")


def _state(base):
    try:
        s = json.loads((base / "alert.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        s = None
    return s if isinstance(s, dict) and isinstance(s.get("alerted"), bool) else {"alerted": False}


def _save(base, state):
    tmp = base / "alert.json.tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps(state, sort_keys=True) + "\n")
    os.replace(tmp, base / "alert.json")


def _send(topic_file, send, title, text, urgent):
    """None when sent, else why not."""
    url, why = topic_url(topic_file)
    if why:
        return why
    try:
        send(url, title, text, urgent=urgent)
    except Exception as e:                              # noqa: BLE001  (unsent: tried again later)
        return f"{type(e).__name__}: {str(e)[:200]}"
    return None


def after_monitor(base, *, topic_file=TOPIC_FILE, send=ntfy, clock=time.gmtime):
    """Called after each monitor run: what was sent ("...: not sent: why" when it could not be), or None."""
    base = Path(base)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", clock())
    fd = os.open(base / ".alert.lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)                  # two monitor runs at once send one message
        state = _state(base)
        out = []
        pending = state.get("pending")
        if isinstance(pending, dict):                   # a recovery that could not be sent before
            if _send(topic_file, send, pending.get("title", ""), pending.get("text", ""), False) is None:
                state.pop("pending")
                out.append(pending.get("title", ""))
        failed, busy, last = streak(_records(base / "monitor.jsonl"))
        message = None
        if failed >= FAILS_IN_A_ROW and not state["alerted"]:
            message = (f"Argus staging: FAIL {failed}x in a row", describe(last), True)
        elif busy >= BUSY_IN_A_ROW and not state["alerted"]:
            message = (f"Argus staging: monitor stuck ({busy} busy runs in a row)",
                       f"no smoke test since {last.get('at') if last else 'ever'}: the data lock stays held", True)
        elif failed == 0 and busy == 0 and last is not None and state["alerted"]:
            message = ("Argus staging: recovered", f"release {last.get('release')}\nmonitor passes again ({now})", False)
        if message:
            title, text, urgent = message
            why = _send(topic_file, send, title, text, urgent)
            if urgent:
                if why is None:
                    state.update(alerted=True, at=now, title=title)
                    state.pop("unsent", None)
                else:
                    state.update(unsent=why, unsent_at=now)        # alerted stays False: tried again next run
            else:
                state.update(alerted=False, at=now, title=title)   # never blocks the next FAIL
                if why is not None:
                    state["pending"] = {"title": title, "text": text}
            out.append(title if why is None else f"{title}: not sent: {why}")
        _save(base, state)
        return "; ".join(out) or None
    finally:
        os.close(fd)
