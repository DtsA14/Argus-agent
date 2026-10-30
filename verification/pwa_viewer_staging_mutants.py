"""Mutants for SPEC_PWA_VIEWER PR 2 (staging and proxy, §4 S and §8 A1-A5): each applied alone in a worktree, the named
tests run with -x; killed = a test failed (an error or a skip is not a kill). Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
V, D = "router/stage_viewer.py", "router/stage_data.py"
T = ["tests/test_stage_viewer.py"]
M = [
    # S2/A5: the address
    ("bind 0.0.0.0", V, 'BIND, PORT = "127.0.0.1", 8710', 'BIND, PORT = "0.0.0.0", 8710', T),
    ("port 8000", V, 'BIND, PORT = "127.0.0.1", 8710', 'BIND, PORT = "127.0.0.1", 8000', T),
    ("listener check accepts any", V, 'return got == [f"{BIND}:{port}"], f"listening: {got}"',
     'return bool(got) and f"{BIND}:{port}" in got, f"listening: {got}"', T),
    # S2: Host, methods
    ("Host not checked", V, 'return len(hosts) == 1 and hosts[0] in (f"localhost:{port}", f"127.0.0.1:{port}")',
     "return True", T),
    ("any port in Host", V, 'return len(hosts) == 1 and hosts[0] in (f"localhost:{port}", f"127.0.0.1:{port}")',
     'return len(hosts) == 1 and hosts[0].split(":")[0] in ("localhost", "127.0.0.1")', T),
    ("two Host headers", V, "return len(hosts) == 1 and hosts", "return len(hosts) >= 1 and hosts", T),
    ("POST answered", V, '            return self._refuse\n', '            return self.do_GET\n', T),
    # A1: the API allowlist
    ("API prefix", V, "            m = API.match(path)", "            m = re.match(r\"^/api/(.*)$\", path)", T),
    ("API query kept", V, 'pattern.strip("^$") + r"))$")', 'pattern.strip("^$") + r"))(?:\\?.*)?$")', T),
    # A2: own headers only
    ("client headers forwarded", V, '                conn.putheader("Connection", "close")\n',
     '                conn.putheader("Connection", "close")\n'
     '                [conn.putheader(k, val) for k, val in self.headers.items() if k.lower() != "host"]\n', T),
    ("client Host forwarded", V, '                conn.putheader("Host", sg.HOST)',
     '                conn.putheader("Host", self.headers.get("Host"))', T),
    # A3: no-store, security headers
    ("no no-store", V, '"no-store" if api else "no-cache"', '"no-cache"', T),
    ("no CSP", V, "        for k, val in SECURITY.items():\n",
     "        for k, val in list(SECURITY.items())[1:]:\n", T),
    # S2: only JSON, only the release's container
    ("not JSON passed", V, "            json.loads(body)\n", "\n", T),
    ("any status passed", V, "if status not in (200, 404) or not ctype", "if not ctype", T),
    ("no peer check", V, 'conn.sock = sg._connect(ledger.dir(live) / "sock" / "app.sock", peer=peer)',
     'conn.sock = sg._connect(ledger.dir(live) / "sock" / "app.sock")', T),
    # S2: files
    ("dot segments", V, "not all(SEGMENT.match(s) and not s.startswith(\".\") for s in segments)",
     "not all(SEGMENT.match(s) for s in segments)", T),
    ("file follows links", V, "ffd = os.open(segments[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)",
     "ffd = os.open(segments[-1], os.O_RDONLY | os.O_NONBLOCK, dir_fd=fd)", T),
    ("dir follows links", V, "            fd = os.open(s, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)",
     "            fd = os.open(s, os.O_RDONLY | os.O_DIRECTORY, dir_fd=fd)", T),
    ("missing asset -> index", V, 'if got is None and (route or "." not in segments[-1]):', "if got is None:", T),
    # A4
    ("symlink in dist", V, "            if not stat.S_ISREG(st.st_mode):\n                problems",
     "            if stat.S_ISFIFO(st.st_mode):\n                problems", T),
    ("hardlink", V, "            if st.st_nlink > 1:", "            if st.st_nlink > 2:", T),
    ("dot names", V, 'if not SEGMENT.match(name) or name.startswith("."):', "if not SEGMENT.match(name):", T),
    ("depth", V, 'if path.count("/") >= MAX_DEPTH:', 'if path.count("/") > MAX_DEPTH:', T),
    ("file size", V, "            if st.st_size > MAX_FILE:", "            if st.st_size > 2 * MAX_FILE:", T),
    ("total", V, "    if total > MAX_TOTAL:", "    if total > 2 * MAX_TOTAL:", T),
    ("count", V, "    if count > MAX_FILES:", "    if count > MAX_FILES + 1:", T),
    ("utf-8", V, '                    data.decode("utf-8")', '                    data.decode("latin-1")', T),
    ("magic", V, "            elif not data.startswith(MAGIC[ext]):", "            elif False:", T),
    ("extension", V, "            if ext not in TYPES:", "            if ext not in TYPES and ext != \".map\" and ext:", T),
    ("key scan", V, "            if sd.KEY.search(data):", "            if False:", T),
    # A3: storage, sw.js
    ("storage in sw.js only", V, '            if m and path != "sw.js":', "            if m and path.endswith('.html'):", T),
    ("sw.js not pinned", V, 'if path == "sw.js" and hashlib.sha256(data).hexdigest() != sw_sha256:',
     'if path == "sw.js" and sw_sha256 and hashlib.sha256(data).hexdigest() != sw_sha256:', T),
    ("sw.js may be missing", V, '("index.html", "sw.js") if p not in found]', '("index.html",) if p not in found]', T),
    # E1
    ("other version", V, "            if version != want or", "            if want is None or", T),
    ("peer deps unchecked", V, "    for kind in DEP_KINDS:", "    for kind in DEP_KINDS[:2]:", T),
    ("E1 not run", V, "                problems = (dependency_problems(package, json.loads(",
     "                problems = ([] if 1 else dependency_problems(package, json.loads(", T),
    ("workspace not checked", V, "                problems += va.vitest_workspace_problems(tmp / \"src\")\n", "", T),
    ("not a viewer job", V, 'if job.data["inputs"].get("environment") != ENVIRONMENT:', "if False:", T),
    # S1: build isolation
    ("build with network", V, '"--network", "none",', '"--network", "bridge",', T),
    ("workspace writable", V, '"-v", f"{src}:/workspace:ro"', '"-v", f"{src}:/workspace"', T),
    # S1: publishing
    ("smoke not a gate", V, "        if not ok:\n            raise Refused(f\"release {release} failed",
     "        if False:\n            raise Refused(f\"release {release} failed", T),
    ("state failure keeps new current", V, "            if old is None:\n                os.unlink(self.base / \"current\")\n"
     "            else:\n                _swap(self.base, old)\n", "            pass\n", T),
    ("smoke asset hash", V, 'return status == 200 and _sha(body) == files.get(ref.lstrip("/")), f"{status} {_sha(body)[:12]}"',
     'return status == 200, f"{status} {_sha(body)[:12]}"', T),
    ("monitor ignores viewer", D, '                if rec["viewer"] and not rec["viewer"]["ok"] and rec["ok"]:',
     "                if False:", T),
    # code review of PR 2
    ("no reconcile", V, '        if self.published() == live and (live is not None or not os.path.lexists(self.base / "current")):
            return',
     "        return", T),
    ("known release not checked again", V, "        problems = artifact_problems(self.dir(release), self.sw_sha256)
        if problems:   ",
     "        problems = []
        if problems:   ", T),
    ("known release on another image", V, 'if known is not None and known.get("image") != image:', "if False:", T),
    ("monitor without the viewer lock", D, "        with viewer.lock():                       # never",
     "        with _nothing():                       # never", T),
    ("relative refs skipped", V, '        ref = posixpath.normpath("/" + ref.removeprefix("./").lstrip("/"))
',
     '        if not ref.startswith("/"):
            continue
', T),
    ("stale pid never refreshed", V, "                if not from_cache:
                    raise
",
     "                raise
", T),
    ("pid never cached", V, "        from_cache = bool(cached) and cached[0] == live", "        from_cache = False", T),
]
# Equivalent, not listed: rollback's own v.verify(previous) before the confirmation (switch() verifies again before
# anything changes; the early call only refuses before asking); a range or path in package.json (never the locked
# version, so `version != want` already refuses it).

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
