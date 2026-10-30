"""A notification when the staging monitor keeps failing (Atha 2026-10-30, after the live release was down for 16 runs
unnoticed): one ntfy message after FAILS_IN_A_ROW failed runs in a row, one when a run passes again; never one per run.

A busy run (ok null: another refresh held the data lock, or the live release changed during the smoke test) is neither
a failure nor a pass: it is skipped. The message names the release(s) and which checks failed and why, as the harness
words it; an answer of the app is reduced to its status ("answered 500"), so no API data leaves the VM. The ntfy topic
is read from a 0600 file outside the repository (never an argument); without one, nothing is sent and the run says so.
State: <staging>/alert.json (0600). A send that fails leaves the alert unsent: the next run tries again.
"""
import json
import os
import re
import stat
import time
import urllib.request
from pathlib import Path

FAILS_IN_A_ROW = 3                                      # 15-minute runs: about 30-45 minutes after it broke
NTFY = "https://ntfy.sh"
TOPIC_FILE = Path.home() / ".ntfy" / "argus_topic"   # not next to the API key file
TOPIC = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
SEND_TIMEOUT_S = 10
STATUS_DETAIL = re.compile(r"^(\d{3}) ")                # "<status> <body or sha>": the app's answer, never sent


def _records(path):
    out = []
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    for line in lines:
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if isinstance(r, dict):
            out.append(r)
    return out


def failures_in_a_row(records):
    """(failed runs since the last pass, the last failed or passed record); busy runs (ok not a bool) are skipped."""
    decided = [r for r in records if isinstance(r.get("ok"), bool)]
    n = 0
    for r in reversed(decided):
        if r["ok"]:
            break
        n += 1
    return n, (decided[-1] if decided else None)


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
        lines.append(f"viewer {viewer.get('release')}")
        lines += _failed(viewer.get("smoke"))
    return "\n".join(lines)


def topic_url(topic_file):
    """The ntfy URL from a private topic file, or (None, why)."""
    p = Path(topic_file)
    try:
        st = os.lstat(p)
    except OSError:
        return None, f"no topic file {p}"
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
        return None, f"{p} is not a regular file"
    if st.st_mode & 0o077:
        return None, f"{p} can be read by others (chmod 600 it)"
    topic = p.read_text(encoding="utf-8").strip()
    if not TOPIC.match(topic):
        return None, f"{p} does not hold a topic name ([A-Za-z0-9_-], 16-64)"
    return f"{NTFY}/{topic}", None


def ntfy(url, title, text):
    """POST the message to ntfy; nothing but the message, its title, priority and tags."""
    req = urllib.request.Request(url, data=text.encode("utf-8"), method="POST", headers={
        "Title": title, "Priority": "high" if "FAIL" in title else "default",
        "Tags": "warning" if "FAIL" in title else "white_check_mark"})
    with urllib.request.urlopen(req, timeout=SEND_TIMEOUT_S) as r:
        if r.status >= 300:
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


def after_monitor(base, *, topic_file=TOPIC_FILE, send=ntfy, clock=time.gmtime):
    """Called after each monitor run: the message sent, "... not sent: why", or None (nothing to send)."""
    base = Path(base)
    state = _state(base)
    n, last = failures_in_a_row(_records(base / "monitor.jsonl"))
    if last is None:
        return None
    if n >= FAILS_IN_A_ROW and not state["alerted"]:
        title, text, alerted = f"Argus staging: FAIL {n}x in a row", describe(last), True
    elif n == 0 and state["alerted"]:
        title, text, alerted = "Argus staging: recovered", f"release {last.get('release')}\nmonitor passes again", False
    else:
        return None
    url, why = topic_url(topic_file)
    try:
        if why:
            raise OSError(why)
        send(url, title, text)
    except Exception as e:                              # noqa: BLE001  (unsent: the next run tries again)
        _save(base, {**state, "unsent": f"{type(e).__name__}: {str(e)[:200]}",
                     "unsent_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", clock())})
        return f"{title}: not sent: {e}"
    _save(base, {"alerted": alerted, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", clock()), "title": title})
    return title
