"""Mutants for SPEC_WEB_TOOLS (ReadDocs): each applied alone in a worktree, the named tests run with -x; killed = a test
failed (an error or a skip is not a kill). Usage: mutants_web.py <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
F, W, T = "tools/web_fetch.py", "tools/web.py", "codetask/tools.py"
TF, TD = "tests/test_web_fetch.py", "tests/test_read_docs.py"
M = [
    ("url: http accepted", F, 'if not isinstance(url, str) or not url.startswith("https://"):',
     'if not isinstance(url, str) or not url.startswith(("https://", "http://", "ftp://")):', [TF]),
    ("url: port accepted", F, "if port is not None or parts.netloc.endswith(\":\"):", "if False:", [TF]),
    ("url: userinfo accepted", F, 'if "@" in parts.netloc:', "if False:", [TF]),
    ("url: query accepted", F, '    if "?" in url:\n', "    if False:\n", [TF]),
    ("url: fragment accepted", F, '    if "#" in url:\n', "    if False:\n", [TF]),
    ("url: subdomains of a host accepted", F, "    if host not in hosts:",
     "    if host not in hosts and not any(host.endswith('.' + h) for h in hosts):", [TF]),
    ("url: path pattern as a prefix", F, "if not re.fullmatch(hosts[host], path):", "if not re.match(hosts[host], path):",
     [TF]),
    ("url: escapes and .. accepted", F, 'if not PATH_CHARS.match(path) or ".." in path.split("/") or "%" in path:',
     "if not re.match(r\"^/[A-Za-z0-9._~/%-]*$\", path):", [TF]),
    ("url: no length limit", F, '    if len(url) > limits["url_len"]:', "    if False:", [TF]),
    ("ip: mapped IPv6 judged as its IPv4", F, "            return False                                     # a real host never resolves",
     "            ip = ip.ipv4_mapped  # mutant", [TF]),
    ("ip: embedded IPv4 forms accepted", F, "        if any(ip in n for n in EMBEDDED_V6):\n            return False",
     "        if False:\n            return False", [TF]),
    ("ip: private instead of global", F, "    return ip.is_global and not ip.is_multicast",
     "    return not ip.is_private", [TF]),
    ("ip: multicast accepted", F, "    return ip.is_global and not ip.is_multicast", "    return ip.is_global", [TF]),
    ("fetch: one public address is enough", F, "if not addrs or not all(ip_ok(a) for a in addrs):",
     "if not addrs or not any(ip_ok(a) for a in addrs):", [TF]),
    ("fetch: redirects not checked", F, "        why = check_url(url, hosts, limits)\n",
     "        why = check_url(url, hosts, limits) if not chain else None\n", [TF]),
    ("fetch: one redirect more", F, 'if len(chain) > limits["redirects"]:', 'if len(chain) > limits["redirects"] + 1:',
     [TF]),
    ("fetch: any status read", F, '        if status != 200:\n', "        if False:\n", [TF]),
    ("fetch: any content type", F, "        if ctype not in TYPES:", "        if False:", [TF]),
    ("fetch: a redirect target repeated in the reason", F,
     '            return refused("redirect_refused", limits, chain)   # a Location the server chose: not repeated',
     '            return {"ok": False, "code": "redirect_refused", "reason": why, "chain": chain}', [TF]),
    ("fetch: an exception's message in the reason", F,
     "                    return refused(code, limits, chain)\n",
     '                    return {"ok": False, "code": code, "reason": str(e), "chain": chain}\n', [TF]),
    ("fetch: no next address", F, '                if code != "connection" or isinstance(e, http.client.HTTPException) or n == len(addrs) - 1:',
     "                if True:", [TF]),
    ("fetch: a TLS error tries the next address", F,
     '                if code != "connection" or isinstance(e, http.client.HTTPException) or n == len(addrs) - 1:',
     '                if code not in ("connection", "tls") or n == len(addrs) - 1:', [TF]),
    ("fetch: 5xx not transient", F, '            return refused("server_error" if 500 <= status <= 599 else "http_status", limits, chain, status=status)',
     '            return refused("http_status", limits, chain, status=status)', [TF]),
    ("fetch: resolved again for the connection", F, "        for n, ip in enumerate(addrs):",
     "        for n, ip in enumerate(list(resolve(parts.netloc))):", [TF]),
    ("fetch: long text cut instead of refused", F,
     '        if len(text) > limits["page_text"]:\n            return refused("text_long", limits, chain)',
     '        text = text[:limits["page_text"]]', [TF]),
    ("tool: a fence the page can close", "codetask/review.py", '    bar = "`" * (longest + 1)', '    bar = "```"', [TD]),
    ("conn: SNI is the address", F, "self.sock = self._context.wrap_socket(sock, server_hostname=self.host)",
     "self.sock = self._context.wrap_socket(sock, server_hostname=self._ip)", [TF]),
    ("conn: connects to the host name", F, "sock = socket.create_connection((self._ip, 443), self.timeout)",
     "sock = socket.create_connection((self.host, 443), self.timeout)", [TF]),
    ("conn: certificate not verified", F, "context=ssl.create_default_context())",
     "context=ssl._create_unverified_context())", [TF]),
    ("text: scripts kept", F, 'SKIP = {"script", "style",', 'SKIP = {"style",', [TF]),
    ("child: environment inherited", W, "subprocess.run(cmd, env={},", "subprocess.run(cmd, env=dict(os.environ),", [TF]),
    ("child: not isolated", W, 'cmd = [sys.executable, "-I", "-S",', 'cmd = [sys.executable, "-S", "-S",', [TF]),
    ("answer: chain not checked", W,
     "    if not isinstance(chain, list) or not all(isinstance(u, str) and wf.check_url(u, hosts, limits) is None\n                                              for u in chain):",
     "    if not isinstance(chain, list):", [TD]),
    ("answer: address not checked", W, "            or not wf.ip_ok(out[\"ip\"]) or", "            or", [TD]),
    ("answer: sha not checked", W,
     '            or hashlib.sha256(out["text"].encode("utf-8")).hexdigest() != out["sha256"]):', "            ):", [TD]),
    ("store: never read back (download again)", W, "        page = self._stored(path)\n        if page is not None:",
     "        page = None\n        if page is not None:", [TD]),
    ("store: downloads per run unlimited", W, '        if len(downloads) >= lim["pages_run"]:', "        if False:", [TD]),
    ("store: no byte reservation", W,
     'if here + lim["page_bytes"] > lim["attempt_bytes"] or total + lim["page_bytes"] > lim["run_bytes"]:',
     'if here > lim["attempt_bytes"] or total > lim["run_bytes"]:', [TD]),
    ("store: a refusal charged 0 bytes", W, 'size = out["bytes"] if out["ok"] else lim["page_bytes"]',
     'size = out["bytes"] if out["ok"] else 0', [TD]),
    ("store: no start record (a crash mid-download is free)", W,
     '        _append(self.ledger_path, {"event": "start", "id": did, "attempt": self.attempt, "url": url})\n', "", [TD]),
    ("store: transient refusals kept", W, '        if out["ok"] or out.get("code") not in wf.TRANSIENT:',
     "        if True:", [TD]),
    ("store: definite refusals not kept", W, '        if out["ok"] or out.get("code") not in wf.TRANSIENT:',
     '        if out["ok"]:', [TD]),
    ("store: an empty page file is an error", W, "        except (OSError, ValueError):\n            return None",
     "        except OSError:\n            return None", [TD]),
    ("journal: a torn line is an error", W, "        except ValueError:\n            continue", "        except KeyError:\n            continue",
     [TD]),
    ("read: pages per attempt unlimited", W, '        if url not in urls and len(urls) >= self.limits["pages_attempt"]:',
     "        if False:", [TD]),
    ("read: text per attempt unlimited", W, '        if used + len(text) > self.limits["attempt_text"]:',
     "        if False:", [TD]),
    ("read: download without text room", W, "        if not text_room:", "        if False:", [TD]),
    ("read: a repeated step counted twice", W, '        served = [s for s in records if s["step"] != step_key]',
     "        served = records", [TD]),
    ("answer: the child's reason passed through", W,
     '        return refusal(wf.reason(code, limits, out.get("status")), chain, code)',
     '        return refusal(str(out.get("reason") or wf.reason(code, limits, out.get("status"))), chain, code)', [TD]),
    ("retry: grant not checked again", "router/job.py",
     '        why = web_problem(cfg.get("web"), contract) if web else None\n        if why:             # the approved grant',
     '        why = None\n        if why:             # the approved grant', [TD]),
    ("retry: network not shown", "router/job.py", "granted at approve; this stage downloads again", "x", [TD]),
    ("grant: a draft may name read_docs", "acceptance/draft.py",
     "    elif isinstance(c.get(\"tools\"), list) and set(c[\"tools\"]) & ct.HUMAN_TOOLS:", "    elif False:", [TD]),
    ("grant: --web ignored by the contract", "acceptance/draft.py", "    if web:\n        c[\"tools\"]", "    if False:\n        c[\"tools\"]",
     [TD]),
    ("grant: approve does not check the environment", "router/job.py",
     '        why = web_problem(cfg.get("web"), c) if web else None', "        why = None", [TD]),
    ("grant: setup does not check again", "codetask/run.py", '            why = web.problem(cfg.get("web"), contract)',
     "            why = None", [TD]),
    ("grant: an environment off the list allowed", W,
     'if v.get("environment") not in (w.get("environments") or [])})', "if False})", [TD]),
]

if __name__ == "__main__":
    killed = 0
    for name, f, old, new, tests in M:
        p = WT / f
        orig = p.read_text()
        assert orig.count(old) == 1, (name, orig.count(old))
        p.write_text(orig.replace(old, new, 1))
        r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *tests], cwd=WT,
                           capture_output=True, text=True)
        p.write_text(orig)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        k = "failed" in last
        killed += k
        fails = [line for line in r.stdout.splitlines() if line.startswith("FAILED")][:1]
        print(f"{'KILLED ' if k else 'SURVIVED'} {name}: {fails or last}", flush=True)
    print(f"RESULT: {killed}/{len(M)} killed")
