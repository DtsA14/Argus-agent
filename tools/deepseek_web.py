"""DeepSeek Search/Fetch client (docs/reviews/SPEC_RESEARCH_JOB.md §8): one request to api.deepseek.com, as JSON.

Standard library only, and run by the harness as a child process (`python -I -S deepseek_web.py`) with an empty
environment. The request comes on stdin, never in argv or the environment, because it carries the API key:
{"key", "kind": "search" | "fetch", "args": {...}, "limits": {"timeout_s", "max_bytes"}}.
It prints one JSON object on stdout:
  {"ok": true, "status": 200, "body": <the provider's JSON>}
  {"ok": false, "reason": "http_error", "status": <code>, "error_body": <bool>}   an error status; error_body: DeepSeek's
                                                                                  own JSON error came with it
  {"ok": false, "reason": "timeout" | "connection" | "too_large" | "bad_json", "status": <code or null>}

Rules: the only host ever connected to is HOST on port 443 (a constant, not part of the request), TLS verified against
it (the default context), no proxy (http.client reads none), no redirect followed. The fetched site is reached by
DeepSeek's servers, never by this machine. The key is sent only as the Authorization header and never printed.
"""
import http.client
import json
import socket
import ssl
import sys

HOST = "api.deepseek.com"
PORT = 443
PATHS = {"search": "/v1/tools/search", "fetch": "/v1/tools/fetch"}


def is_error_body(raw):
    """DeepSeek's error answer: a JSON object with an "error" object (OpenAI-compatible). A proxy's HTML page is not."""
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return False
    return isinstance(parsed, dict) and isinstance(parsed.get("error"), dict)


def valid_limits(limits):
    return (isinstance(limits, dict) and isinstance(limits.get("timeout_s"), (int, float))
            and not isinstance(limits.get("timeout_s"), bool) and limits["timeout_s"] > 0
            and isinstance(limits.get("max_bytes"), int) and not isinstance(limits.get("max_bytes"), bool)
            and limits["max_bytes"] > 0)


def request(kind, args, key, limits, *, connection=None):
    """One POST to HOST -> the result object described above. Never raises for network or provider errors."""
    body = json.dumps(args).encode("utf-8")
    connection = connection or http.client.HTTPSConnection
    conn = connection(HOST, PORT, timeout=limits["timeout_s"], context=ssl.create_default_context())
    status = None
    try:
        conn.request("POST", PATHS[kind], body=body,
                     headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                              "Accept": "application/json", "User-Agent": "argus-research/1"})
        resp = conn.getresponse()
        status = resp.status
        raw = resp.read(limits["max_bytes"] + 1)
    except (socket.timeout, TimeoutError):
        return {"ok": False, "reason": "timeout", "status": status}
    except (OSError, http.client.HTTPException):
        return {"ok": False, "reason": "connection", "status": status}
    finally:
        conn.close()
    if status != 200:
        return {"ok": False, "reason": "http_error", "status": status, "error_body": is_error_body(raw)}
    if len(raw) > limits["max_bytes"]:
        return {"ok": False, "reason": "too_large", "status": status}
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return {"ok": False, "reason": "bad_json", "status": status}
    if not isinstance(parsed, dict):
        return {"ok": False, "reason": "bad_json", "status": status}
    return {"ok": True, "status": status, "body": parsed}


def main(stdin=sys.stdin, stdout=sys.stdout):
    try:
        req = json.loads(stdin.read())
        kind, args, key, limits = req["kind"], req["args"], req["key"], req["limits"]
        if (kind not in PATHS or not isinstance(args, dict) or not isinstance(key, str) or not key
                or not valid_limits(limits)):
            raise ValueError
    except (ValueError, KeyError, TypeError):
        stdout.write(json.dumps({"ok": False, "reason": "bad_request", "status": None}))
        return 2
    stdout.write(json.dumps(request(kind, args, key, limits)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
