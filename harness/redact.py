"""API key values never reach a log or an error text (FIX-C D7).

A provider's error can echo the request it rejected, headers included. Every key the harness hands to a client is
registered here (models/registry.py `_api_key`), and the two places text leaves the process through the harness, the event
log and a failed model call's message, replace every registered value with a marker. A value shorter than MIN_LEN is never
registered (a placeholder like "unused" would blank ordinary words). This is a net under the code, not a reason to put a
key in a string: the keys stay in environment variables and key files.
"""
import base64
import sys
import threading
import urllib.parse

MIN_LEN = 8
MARK = "[redacted]"
_lock = threading.Lock()
_secrets = set()
_ordered = ()                  # the registered values, longest first, rebuilt when one is added (scrub runs for every string of every event)


def _base64_forms(key):
    """The base64 of the key alone, and the part of the base64 of `<anything>key<anything>` that does not depend on what
    surrounds it (HTTP Basic carries user:key; the three alignments of the key inside the 3-byte groups give three texts).
    A part shorter than MIN_LEN is dropped, so a key under about 12 characters is only hidden alone."""
    raw = key.encode("utf-8")
    out = {base64.b64encode(raw).decode("ascii")}
    for pad in (0, 1, 2):
        enc = base64.b64encode(b"\0" * pad + raw).decode("ascii").rstrip("=")
        groups = (pad + len(raw)) // 3                 # the groups fully inside filler + key; the first has filler in it
        out.add(enc[(4 if pad else 0):4 * groups])
    return {f for f in out if len(f) >= MIN_LEN}


def register(secret):
    """Remember a key value so that scrub() hides it, and its base64 and URL-encoded forms (a header or a URL may carry those).
    Anything that is not a long enough string is ignored."""
    if isinstance(secret, str) and len(secret.strip()) >= MIN_LEN:
        key = secret.strip()
        forms = {key, urllib.parse.quote(key, safe="")} | _base64_forms(key)
        global _ordered
        with _lock:
            _secrets.update(f for f in forms if len(f) >= MIN_LEN)
            _ordered = tuple(sorted(_secrets, key=len, reverse=True))


def scrub(text):
    """text with every registered key value replaced by MARK (longest first, so a key that contains another is hidden
    whole); anything that is not a string comes back unchanged."""
    if not isinstance(text, str) or not text:
        return text
    for s in _ordered:
        if s in text:
            text = text.replace(s, MARK)
    return text


def scrub_value(obj):
    """obj with every string in it scrubbed (dict keys and values, lists and tuples, at any depth); other values are
    returned as they are. This is what the event log uses: the values are cleaned before they are serialised, so a key
    that json would escape (a quote or a backslash in it) is still found, and a value that happens to equal a piece of
    JSON syntax cannot damage the record."""
    if isinstance(obj, str):
        return scrub(obj)
    if isinstance(obj, dict):
        return {scrub_value(k): scrub_value(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [scrub_value(v) for v in obj]
    return obj


class _Scrubbing:
    """A text stream that hides registered key values from what is written to it: the traceback of a chained exception (the provider's
    text sits in `__cause__`) and every print of an error go through it. A value split across two writes is not seen; a line is one write."""

    def __init__(self, stream):
        self._stream = stream

    def write(self, text):
        if not isinstance(text, str):
            return self._stream.write(text)
        self._stream.write(scrub(text))
        return len(text)                  # what the caller handed over: a replaced key must not look like a short write

    def writelines(self, lines):
        for line in lines:
            self.write(line)

    def __getattr__(self, name):
        return getattr(self._stream, name)


def install():
    """Wrap sys.stdout and sys.stderr (once) so that nothing registered is printed. Called by the command line, not by tests."""
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name)
        if not isinstance(stream, _Scrubbing):
            setattr(sys, name, _Scrubbing(stream))


def uninstall():
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name)
        if isinstance(stream, _Scrubbing):
            setattr(sys, name, stream._stream)


def clear():
    """Forget every registered value (tests)."""
    global _ordered
    with _lock:
        _secrets.clear()
        _ordered = ()
