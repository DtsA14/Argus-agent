"""API key values never reach a log or an error text (FIX-C D7).

A provider's error can echo the request it rejected, headers included. Every key the harness hands to a client is
registered here (models/registry.py `_api_key`), and the two places text leaves the process through the harness, the event
log and a failed model call's message, replace every registered value with a marker. A value shorter than MIN_LEN is never
registered (a placeholder like "unused" would blank ordinary words). This is a net under the code, not a reason to put a
key in a string: the keys stay in environment variables and key files.
"""
import threading

MIN_LEN = 8
MARK = "[redacted]"
_lock = threading.Lock()
_secrets = set()


def register(secret):
    """Remember a key value so that scrub() hides it. Anything that is not a long enough string is ignored."""
    if isinstance(secret, str) and len(secret.strip()) >= MIN_LEN:
        with _lock:
            _secrets.add(secret.strip())


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


def clear():
    """Forget every registered value (tests)."""
    with _lock:
        _secrets.clear()
