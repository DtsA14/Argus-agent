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


def register(secret):
    """Remember a key value so that scrub() hides it, and its base64 and URL-encoded forms (a header or a URL may carry those).
    Anything that is not a long enough string is ignored."""
    if isinstance(secret, str) and len(secret.strip()) >= MIN_LEN:
        key = secret.strip()
        forms = {key, base64.b64encode(key.encode("utf-8")).decode("ascii"), urllib.parse.quote(key, safe="")}
        with _lock:
            _secrets.update(f for f in forms if len(f) >= MIN_LEN)


def scrub(text):
    """text with every registered key value replaced by MARK (longest first, so a key that contains another is hidden
    whole); anything that is not a string comes back unchanged."""
    if not isinstance(text, str) or not text:
        return text
    with _lock:
        secrets = sorted(_secrets, key=len, reverse=True)
    for s in secrets:
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
        return self._stream.write(scrub(text) if isinstance(text, str) else text)

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
    with _lock:
        _secrets.clear()
