"""ReadDocs downloader (docs/reviews/SPEC_WEB_TOOLS.md): one documentation page from an allowlisted host, as text.

Standard library only, and run by the harness as a child process (`python -I -S web_fetch.py <request json>`) with an
empty environment: no API key and no proxy setting can reach it. It prints one JSON object on stdout:
{"ok": true, url, final_url, chain, status, content_type, bytes, ip, sha256, text} or {"ok": false, reason, chain}.

Rules (each checked here, before any connection where it can be):
- the URL: https, an exact allowlisted host, no port, no userinfo, no query, no fragment, a plain path ([A-Za-z0-9._~/-],
  no "..", no percent-encoding) matching the host's path pattern, at most url_len characters;
- the host is resolved once per hop and every address must be global (IPv4-mapped, IPv4-compatible, 6to4, NAT64 and
  Teredo forms refused outright); the connection goes to the first checked address (http.client never resolves again) with
  TLS verified against the real host name (the default context: CERT_REQUIRED, check_hostname);
- redirects are not followed by the client: each Location is checked with every rule above, at most `redirects` hops;
- one page is at most page_bytes, within timeout_s for all its hops, of a text content type; its text at most page_text
  characters. Anything that does not fit is a refusal, never a partial page.
- a refusal is a code from REASONS, rendered from a fixed template with the harness's own values (limits, the HTTP status
  number): never text the server chose (a header, an error message, a redirect target), which would reach the model
  outside the fence.
"""
import hashlib
import html.parser
import http.client
import ipaddress
import json
import re
import socket
import ssl
import sys
import time
from urllib.parse import urljoin, urlsplit

PATH_CHARS = re.compile(r"^/[A-Za-z0-9._~/-]*$")
TYPES = {"text/html", "text/plain", "application/json"}
REDIRECTS = {301, 302, 303, 307, 308}
USER_AGENT = "argus-readdocs/1"
EMBEDDED_V6 = [ipaddress.ip_network(n) for n in ("2002::/16", "64:ff9b::/96", "64:ff9b:1::/48", "2001::/32")]


class TooLarge(Exception):
    pass


# Every refusal after the agent's own URL passed check_url. Transient ones (TRANSIENT) are not kept for the run.
REASONS = {
    "url": "the URL is not allowed",
    "redirect_refused": "the page redirects to a URL that is not allowed",
    "redirects": "the page redirects more than {redirects} times",
    "resolve": "the host could not be resolved",
    "address": "the host has an address that is not public",
    "connection": "the connection to the host failed",
    "tls": "the host's TLS certificate was not accepted",
    "timeout": "the page did not arrive within {timeout_s} seconds",
    "too_large": "the page is larger than {page_bytes} bytes",
    "http_status": "the host answered HTTP {status}",
    "server_error": "the host answered HTTP {status} (a server error; it may work later)",
    "content_type": "the page is not text/html, text/plain or application/json",
    "decode": "the page could not be read as its content type",
    "text_long": "the page text is longer than {page_text} characters",
    "failed": "the downloader failed",
}
TRANSIENT = {"resolve", "connection", "timeout", "server_error", "failed"}


def reason(code, limits, status=None):
    """The text of a refusal code, from the harness's values only."""
    st = status if isinstance(status, int) and not isinstance(status, bool) and 100 <= status <= 599 else "?"
    return REASONS.get(code, "the downloader refused the page").format(status=st, **limits)


def refused(code, limits, chain, status=None):
    return {"ok": False, "code": code, "reason": reason(code, limits, status), "chain": chain,
            **({"status": status} if status is not None else {})}


def now():
    return time.monotonic()


def check_url(url, hosts, limits):
    """None when `url` may be fetched, else why not. hosts: {exact host: full-match path regex}."""
    if not isinstance(url, str) or not url.startswith("https://"):
        return "only https URLs are read"
    if len(url) > limits["url_len"]:
        return f"the URL is too long (more than {limits['url_len']} characters)"
    if "#" in url:
        return "a URL with a fragment (#) is not read"
    if "?" in url:
        return "a URL with a query (?) is not read"
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return "the URL does not parse (port)"
    if "@" in parts.netloc:
        return "a URL with userinfo (user@) is not read"
    if port is not None or parts.netloc.endswith(":"):
        return "a URL with a port is not read"
    host = parts.netloc
    if host not in hosts:
        return f"the host {host!r} is not on the allowlist"
    path = parts.path or "/"
    if not PATH_CHARS.match(path) or ".." in path.split("/") or "%" in path:
        return "the path may only use letters, digits and . _ ~ / -, without .. or %-escapes"
    if not re.fullmatch(hosts[host], path):
        return f"the path is not one of the allowed pages of {host}"
    return None


def ip_ok(text):
    """Whether one resolved address may be connected to: global, not multicast, embedded IPv4 judged as itself."""
    try:
        ip = ipaddress.ip_address(text.split("%", 1)[0])
    except ValueError:
        return False
    if ip.version == 6:
        if ip.ipv4_mapped is not None:
            return False                                     # a real host never resolves to ::ffff:a.b.c.d
        if any(ip in n for n in EMBEDDED_V6):
            return False                                     # 6to4, NAT64, Teredo: an IPv4 address in disguise
        elif ip in ipaddress.ip_network("::/96"):
            return False                                     # IPv4-compatible (deprecated) and :: itself
    return ip.is_global and not ip.is_multicast


def resolve(host):
    """Every address of `host` for TCP on 443 (one lookup)."""
    return list(dict.fromkeys(a[4][0] for a in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)))


class _Pinned(http.client.HTTPSConnection):
    """An HTTPS connection to a given address, TLS verified against the real host name; never resolves the host."""

    def __init__(self, host, ip, timeout):
        super().__init__(host, 443, timeout=timeout, context=ssl.create_default_context())
        self._ip = ip

    def connect(self):
        sock = socket.create_connection((self._ip, 443), self.timeout)
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except BaseException:
            sock.close()
            raise


def get_once(host, ip, path, *, deadline, max_bytes):
    """One GET of https://host/path at `ip` -> (status, {lower header: value}, body). TooLarge past max_bytes."""
    left = deadline - now()
    if left <= 0:
        raise socket.timeout("timed out")
    conn = _Pinned(host, ip, timeout=left)
    try:
        conn.request("GET", path, headers={"User-Agent": USER_AGENT, "Accept": "text/html, text/plain, application/json",
                                           "Accept-Encoding": "identity", "Connection": "close"})
        resp = conn.getresponse()
        headers = {k.lower(): v for k, v in resp.getheaders()}
        size = headers.get("content-length")
        if size is not None and size.isdigit() and int(size) > max_bytes:
            raise TooLarge(f"more than {max_bytes} bytes")
        body = b""
        while True:
            if now() > deadline:
                raise socket.timeout("timed out")
            chunk = resp.read(65536)
            if not chunk:
                break
            body += chunk
            if len(body) > max_bytes:
                raise TooLarge(f"more than {max_bytes} bytes")
        return resp.status, headers, body
    finally:
        conn.close()


class _Text(html.parser.HTMLParser):
    SKIP = {"script", "style", "nav", "header", "footer", "noscript", "svg", "template"}
    BLOCK = {"p", "div", "section", "article", "li", "ul", "ol", "table", "tr", "br", "dt", "dd", "dl", "blockquote",
             "h1", "h2", "h3", "h4", "h5", "h6", "pre"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip, self.pre = [], 0, 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif not self.skip:
            if tag in self.BLOCK:
                self.out.append("\n")
            if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
                self.out.append("#" * int(tag[1]) + " ")
            if tag == "pre":
                self.pre += 1

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
        elif not self.skip:
            if tag == "pre":
                self.pre = max(0, self.pre - 1)
            if tag in self.BLOCK:
                self.out.append("\n")

    def handle_data(self, data):
        if self.skip:
            return
        self.out.append(data if self.pre else re.sub(r"\s+", " ", data))


def to_text(body, content_type):
    """The page as text: HTML without scripts, styles and navigation (pre kept), JSON pretty-printed, text as is."""
    raw = body.decode("utf-8", "replace")
    if content_type == "application/json":
        return json.dumps(json.loads(raw), indent=1, sort_keys=True)
    if content_type == "text/plain":
        return raw
    p = _Text()
    p.feed(raw)
    p.close()
    lines = [line.rstrip() if line.strip() else "" for line in "".join(p.out).split("\n")]
    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip("\n")


def _code(e):
    """The refusal code of an exception; never its message (it may carry text the server sent)."""
    if isinstance(e, ssl.SSLError):
        return "tls"
    if isinstance(e, (socket.timeout, TimeoutError)):
        return "timeout"
    if isinstance(e, TooLarge):
        return "too_large"
    return "connection"


def fetch(url, hosts, limits, *, resolve=resolve, get=get_once):
    """The whole fetch of one URL with its redirects -> the result object (see the module docstring)."""
    chain, deadline = [], now() + limits["timeout_s"]
    while True:
        why = check_url(url, hosts, limits)
        if why:
            if not chain:                                   # the agent's own URL: its reason names only what it wrote
                return {"ok": False, "code": "url", "reason": why, "chain": chain}
            return refused("redirect_refused", limits, chain)   # a Location the server chose: not repeated
        chain.append(url)
        parts = urlsplit(url)
        try:
            addrs = list(resolve(parts.netloc))
        except OSError:
            return refused("resolve", limits, chain)
        if not addrs or not all(ip_ok(a) for a in addrs):
            return refused("address", limits, chain)
        for n, ip in enumerate(addrs):                      # the next checked address only if this one did not connect
            try:
                status, headers, body = get(parts.netloc, ip, parts.path or "/", deadline=deadline,
                                            max_bytes=limits["page_bytes"])
                break
            except (OSError, http.client.HTTPException, TooLarge, ssl.SSLError) as e:
                code = _code(e)
                if code != "connection" or isinstance(e, http.client.HTTPException) or n == len(addrs) - 1:
                    return refused(code, limits, chain)
        if status in REDIRECTS:
            if len(chain) > limits["redirects"]:
                return refused("redirects", limits, chain)
            url = urljoin(url, headers.get("location") or "")
            continue
        if status != 200:
            return refused("server_error" if 500 <= status <= 599 else "http_status", limits, chain, status=status)
        ctype = (headers.get("content-type") or "").split(";", 1)[0].strip().lower()
        if ctype not in TYPES:
            return refused("content_type", limits, chain)
        try:
            text = to_text(body, ctype)
        except ValueError:
            return refused("decode", limits, chain)
        if len(text) > limits["page_text"]:
            return refused("text_long", limits, chain)
        return {"ok": True, "url": chain[0], "final_url": url, "chain": chain, "status": status, "content_type": ctype,
                "bytes": len(body), "ip": ip, "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), "text": text}


def main(argv):
    if argv[1:] == ["--env"]:                                # the tests' check that the child sees no environment
        import os
        print(json.dumps(dict(os.environ)))
        return 0
    try:
        req = json.loads(argv[1])
        out = fetch(req["url"], req["hosts"], req["limits"])
    except Exception:                                        # one JSON answer, whatever happened
        out = {"ok": False, "code": "failed", "reason": REASONS["failed"], "chain": []}
    sys.stdout.write(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
