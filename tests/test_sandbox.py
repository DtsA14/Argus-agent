"""Phase 2d: the Docker sandbox, tested in a real container.

These tests check the *effect* of every hardening flag from inside the container, not just that the
flag was passed. They need Docker and a pinned image (ARGUS_SANDBOX_IMAGE or sandbox.image). Without
them they are skipped with "SANDBOX NOT AVAILABLE", and scripts/verify.sh then FAILS unless
ARGUS_SANDBOX_OPTIONAL=1: a skipped sandbox test does not count as passing.
"""
import copy
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

from dataset import CSV_PATH
from harness.events import EventLog
from tools import sandbox as sb

CFG = {"kind": "docker", "memory": "256m", "cpus": "1", "pids": 64, "timeout_s": 20, "max_output_bytes": 4096}


@pytest.fixture(scope="module")
def cfg():
    ok, reason = sb.status(CFG)
    if not ok:
        pytest.skip(f"SANDBOX NOT AVAILABLE: {reason}")
    return dict(CFG)


def run(cfg, code, tmp_path, **over):
    c = {**cfg, **over}
    return sb.run_python(code, workdir=tmp_path / "ws", data_dir=CSV_PATH.parent, cfg=c,
                         log=EventLog(tmp_path / "e.jsonl"))


def probe(cfg, tmp_path, code):
    r = run(cfg, code, tmp_path)
    assert r["exit_code"] == 0, r
    return json.loads(r["stdout"])


# ---- the code actually runs (regression: without -i Docker drops stdin and "succeeds") ----------

def test_code_runs_and_reads_the_data(cfg, tmp_path):
    r = run(cfg, "import csv\nrows=list(csv.DictReader(open('/data/penjualan.csv')))\n"
                 "print(len(rows), sum(int(x['omzet']) for x in rows))", tmp_path)
    import dataset
    rows = dataset.load_rows()
    assert r["exit_code"] == 0 and r["stdout"].split() == [str(len(rows)), str(sum(x["omzet"] for x in rows))]


def test_code_that_prints_nothing_is_not_mistaken_for_success_of_other_code(cfg, tmp_path):
    r = run(cfg, "raise SystemExit(3)", tmp_path)
    assert r["exit_code"] == 3


# ---- isolation, checked from inside ---------------------------------------------------------------

ID_PROBE = """
import json, os
st = dict(l.split(':', 1) for l in open('/proc/self/status').read().splitlines() if ':' in l)
print(json.dumps({"uid": os.getuid(), "gid": os.getgid(), "cap_eff": st['CapEff'].strip(),
                  "cap_bnd": st['CapBnd'].strip(), "no_new_privs": st['NoNewPrivs'].strip()}))
"""


def test_runs_as_nobody_without_capabilities_or_privilege_escalation(cfg, tmp_path):
    p = probe(cfg, tmp_path, ID_PROBE)
    assert (p["uid"], p["gid"]) == (65534, 65534)
    assert int(p["cap_eff"], 16) == 0
    # A non-root user has CapEff 0 anyway; the bounding set shows whether --cap-drop ALL really applied
    assert int(p["cap_bnd"], 16) == 0
    assert p["no_new_privs"] == "1"


def test_no_network(cfg, tmp_path):
    p = probe(cfg, tmp_path, """
import json, socket
res = {}
for host, port in (("1.1.1.1", 53), ("8.8.8.8", 443)):
    try:
        socket.create_connection((host, port), timeout=2); res[host] = "open"
    except OSError as e:
        res[host] = type(e).__name__
ifaces = [l.split(':')[0].strip() for l in open('/proc/net/dev').read().splitlines()[2:]]
print(json.dumps({"conn": res, "ifaces": ifaces}))
""")
    assert "open" not in p["conn"].values()
    assert p["ifaces"] == ["lo"]                      # only loopback exists


def test_filesystem_is_read_only_except_workspace_and_tmp(cfg, tmp_path):
    p = probe(cfg, tmp_path, """
import json
res = {}
for path in ('/etc/x', '/usr/x', '/x', '/data/x', '/data/penjualan.csv', '/workspace/out.txt', '/tmp/t'):
    try:
        open(path, 'a').write('x'); res[path] = 'writable'
    except OSError as e:
        res[path] = type(e).__name__
print(json.dumps(res))
""")
    writable = {k for k, v in p.items() if v == "writable"}
    assert writable == {"/workspace/out.txt", "/tmp/t"}
    # Permissions alone would already stop nobody from writing /etc or /data; check the mounts themselves
    # so the test fails if --read-only or the :ro data mount is ever dropped.
    mounts = probe(cfg, tmp_path, """
import json
m = {}
for line in open('/proc/self/mounts'):
    dev, point, fstype, opts = line.split()[:4]
    m[point] = opts.split(',')[0]
print(json.dumps(m))
""")
    assert mounts["/"] == "ro"
    assert mounts["/data"] == "ro"
    assert mounts["/workspace"] == "rw" and mounts["/tmp"] == "rw"
    assert (tmp_path / "ws" / "out.txt").read_text() == "x"            # workspace is the host dir
    assert CSV_PATH.read_text().endswith("\n")                          # data untouched


def test_limits_are_really_active_in_the_cgroup(cfg, tmp_path):
    p = probe(cfg, tmp_path, """
import json
def first(*paths):
    for p in paths:
        try: return open(p).read().strip()
        except OSError: pass
print(json.dumps({
  "mem": first('/sys/fs/cgroup/memory.max', '/sys/fs/cgroup/memory/memory.limit_in_bytes'),
  "pids": first('/sys/fs/cgroup/pids.max', '/sys/fs/cgroup/pids/pids.max'),
  "cpu": first('/sys/fs/cgroup/cpu.max', '/sys/fs/cgroup/cpu/cpu.cfs_quota_us'),
}))
""")
    assert int(p["mem"]) == 256 * 1024 * 1024
    assert int(p["pids"]) == 64
    quota = p["cpu"].split()[0]                      # cgroup v2: "100000 100000"; v1: "100000"
    assert quota != "max" and int(quota) == 100000   # 1 CPU


def test_memory_limit_kills_the_code(cfg, tmp_path):
    r = run(cfg, "b = bytearray(512 * 1024 * 1024)\nprint('ALLOCATED')", tmp_path)
    assert r["exit_code"] == 137 and r["killed"] and "ALLOCATED" not in r["stdout"]


def test_fork_bomb_is_stopped_by_the_pids_limit(cfg, tmp_path):
    r = run(cfg, """
import os, time
n = 0
try:
    for _ in range(500):
        if os.fork() == 0:
            time.sleep(3); os._exit(0)
        n += 1
except OSError as e:
    print('refused after', n)
""", tmp_path)
    assert r["exit_code"] == 0 and r["stdout"].startswith("refused after")
    assert int(r["stdout"].split()[-1]) < 64


def test_timeout_kills_and_removes_the_container(cfg, tmp_path):
    r = run(cfg, "import time\nprint('start', flush=True)\ntime.sleep(60)", tmp_path, timeout_s=3)
    assert r["timed_out"] and r["exit_code"] is None
    name = [json.loads(l) for l in (tmp_path / "e.jsonl").read_text().splitlines()][-1]["container"]
    left = subprocess.run(["docker", "ps", "-a", "--filter", f"name={name}", "--format", "{{.Names}}"],
                          capture_output=True, text=True).stdout.strip()
    assert left == ""
    assert r["cleanup_failed"] is False


HUNG_DOCKER = """#!/bin/bash
# Real docker for run / image inspect; a daemon that never answers for kill, rm and ps.
case "$1" in
  kill|rm|ps) exec sleep 300 ;;
  *) exec docker "$@" ;;
esac
"""


def test_cleanup_is_bounded_and_reported_when_the_daemon_hangs(cfg, tmp_path):
    # GPT review of the 2d patch: kill / rm each had their own 30 s timeout plus unbounded waits, so a
    # hung daemon could stretch one call far past timeout_s. Cleanup now shares one cleanup_timeout_s
    # budget, and a container whose removal is not confirmed is reported, not silently assumed gone.
    fake = tmp_path / "docker"
    fake.write_text(HUNG_DOCKER)
    fake.chmod(0o755)
    t = time.monotonic()
    r = run(cfg, "import time\nprint('start', flush=True)\ntime.sleep(300)", tmp_path,
            docker=str(fake), timeout_s=2, cleanup_timeout_s=3)
    elapsed = time.monotonic() - t
    events = [json.loads(l) for l in (tmp_path / "e.jsonl").read_text().splitlines()]
    failed = [e for e in events if e["event"] == "sandbox_cleanup_failed"]
    try:
        assert elapsed < 2 + 3 + 4, elapsed            # timeout + cleanup budget + slack, not 2 + 60+
        assert r["timed_out"] and r["cleanup_failed"] is True
        assert failed and failed[0]["container"].startswith("argus-")
        assert events[-1]["cleanup_failed"] is True    # also on the sandbox_run event
    finally:
        subprocess.run(["docker", "rm", "-f", *subprocess.run(
            ["docker", "ps", "-aq", "--filter", "label=argus.sandbox=1"],
            capture_output=True, text=True).stdout.split()], capture_output=True)


def test_output_is_capped(cfg, tmp_path):
    r = run(cfg, "print('x' * 100000)", tmp_path)
    assert r["truncated"] and len(r["stdout"].encode()) <= 4096
    assert r["stdout_bytes"] == 100001


# ---- output is bounded in the HOST process, not only in what is returned (audit 2d, P1) ------------
# Before the fix, subprocess.run(capture_output=True) held all output in harness memory and only then
# cut it: 400 MB printed in the container cost the harness 1.2 GB of RSS.

FLOOD = "import sys\nb = b'x' * (1 << 20)\nfor _ in range({mb}): sys.stdout.buffer.write(b)\n"

RSS_PROBE = """
import json, os, resource, sys, tempfile
sys.path.insert(0, os.getcwd())
from tools import sandbox as sb
cfg = json.loads(sys.argv[1]); code = sys.argv[2]
base = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
r = sb.run_python(code, workdir=tempfile.mkdtemp(), data_dir=tempfile.mkdtemp(), cfg=cfg)
peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
r.pop("stdout"); r.pop("stderr")
print(json.dumps({"growth_kb": peak - base, **r}))
"""


def harness_rss(cfg, code):
    """Run the sandbox from a fresh Python process and report how much that process's peak RSS grew."""
    p = subprocess.run([sys.executable, "-c", RSS_PROBE, json.dumps(cfg), code],
                       capture_output=True, text=True, timeout=120, cwd=Path(__file__).resolve().parents[1])
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


def test_huge_output_is_drained_without_growing_harness_memory(cfg):
    # 256 MB to stdout, early kill disabled: the reader must drain all of it (no deadlock, exit 0)
    # while the harness keeps only max_output_bytes.
    r = harness_rss({**cfg, "kill_after_output_bytes": 1 << 40, "timeout_s": 60}, FLOOD.format(mb=256))
    assert r["exit_code"] == 0 and not r["timed_out"] and not r["output_limit_exceeded"]
    assert r["stdout_bytes"] == 256 << 20 and r["truncated"]
    assert r["growth_kb"] < 32 * 1024, r                 # was ~3x the output (768 MB) before the fix


def test_output_past_the_limit_is_drained_so_the_code_keeps_running(cfg, tmp_path):
    # If the reader stopped at the limit, the pipe would fill, the write would block, and the code
    # would never reach the lines after it: it would end only by timeout.
    r = run(cfg, "import sys\nsys.stdout.write('x' * (8 << 20)); sys.stdout.flush()\n"
                 "open('/workspace/after.txt', 'w').write('ok')\nsys.stderr.write('done')",
            tmp_path, kill_after_output_bytes=1 << 40)
    assert r["exit_code"] == 0 and not r["timed_out"]
    assert (tmp_path / "ws" / "after.txt").read_text() == "ok"
    assert r["stderr"] == "done" and r["stdout_bytes"] == 8 << 20


def test_stderr_is_bounded_too(cfg):
    r = harness_rss({**cfg, "kill_after_output_bytes": 1 << 40},
                    "import sys\nb = b'e' * (1 << 20)\nfor _ in range(128): sys.stderr.buffer.write(b)\n")
    assert r["exit_code"] == 0 and r["stderr_bytes"] == 128 << 20 and r["truncated"]
    assert r["growth_kb"] < 32 * 1024, r


def test_endless_output_kills_the_container_early_and_removes_it(cfg, tmp_path):
    t = time.monotonic()
    r = run(cfg, "while True: print('x' * 1000)", tmp_path, kill_after_output_bytes=1 << 20, timeout_s=20)
    assert time.monotonic() - t < 10                     # killed for flooding, not at the 20 s timeout
    assert r["output_limit_exceeded"] and not r["timed_out"] and not r["killed"]
    assert r["truncated"] and len(r["stdout"].encode()) <= 4096
    assert container_gone(tmp_path)


def test_timeout_still_kills_and_removes_after_large_output(cfg, tmp_path):
    r = run(cfg, "import sys, time\nsys.stdout.write('x' * (4 << 20)); sys.stdout.flush()\ntime.sleep(60)",
            tmp_path, timeout_s=3, kill_after_output_bytes=1 << 40)
    assert r["timed_out"] and r["exit_code"] is None and r["truncated"]
    assert r["stdout_bytes"] == 4 << 20 and len(r["stdout"].encode()) <= 4096
    assert container_gone(tmp_path)


def test_container_output_is_not_logged_to_the_host_disk(cfg, tmp_path):
    # Found while testing P1: the default json-file log driver writes all output to /var/lib/docker on
    # the host, unbounded, regardless of how the harness reads the pipes (a flooding container filled
    # the disk during a mutation run). Check the running container's real log config.
    import threading
    box = {}
    t = threading.Thread(target=lambda: box.update(r=run(cfg, "import time\nprint('hi', flush=True)\n"
                                                              "time.sleep(4)", tmp_path)))
    t.start()
    ids = ""
    for _ in range(60):
        ids = subprocess.run(["docker", "ps", "-q", "--filter", "label=argus.sandbox=1"],
                             capture_output=True, text=True).stdout.split()
        if ids:
            break
        time.sleep(0.1)
    log_type = subprocess.run(["docker", "inspect", "--format", "{{.HostConfig.LogConfig.Type}}", ids[0]],
                              capture_output=True, text=True).stdout.strip()
    t.join()
    assert log_type == "none"
    assert box["r"]["exit_code"] == 0 and box["r"]["stdout"] == "hi\n"   # attach still delivers output


def test_invalid_utf8_output_does_not_crash_the_harness(cfg, tmp_path):
    r = run(cfg, "import sys\nsys.stdout.buffer.write(b'ok \\xff\\xfe end')", tmp_path)
    assert r["exit_code"] == 0 and r["stdout"].startswith("ok ") and r["stdout"].endswith(" end")


def container_gone(tmp_path):
    name = [json.loads(l) for l in (tmp_path / "e.jsonl").read_text().splitlines()][-1]["container"]
    left = subprocess.run(["docker", "ps", "-a", "--filter", f"name={name}", "--format", "{{.Names}}"],
                          capture_output=True, text=True).stdout.strip()
    return left == ""


# ---- no unsandboxed fallback, pinned images only ---------------------------------------------------

def test_unpinned_image_is_refused_and_nothing_runs(tmp_path, monkeypatch):
    monkeypatch.setenv("ARGUS_SANDBOX_IMAGE", "python:3.13-slim")
    marker = tmp_path / "ran"
    with pytest.raises(sb.SandboxUnavailable, match="not pinned"):
        sb.run_python(f"open({str(marker)!r}, 'w')", workdir=tmp_path / "ws", data_dir=CSV_PATH.parent,
                      cfg={"kind": "docker"})
    assert not marker.exists()


def test_missing_docker_never_falls_back_to_the_host(tmp_path, monkeypatch):
    monkeypatch.setenv("ARGUS_SANDBOX_IMAGE", "sha256:" + "0" * 64)
    marker = tmp_path / "ran"
    with pytest.raises(sb.SandboxUnavailable):
        sb.run_python(f"open({str(marker)!r}, 'w')", workdir=tmp_path / "ws", data_dir=CSV_PATH.parent,
                      cfg={"kind": "docker", "docker": "/nonexistent/docker"})
    assert not marker.exists()                       # the code never ran on the host


def test_graph_refuses_to_start_when_the_sandbox_is_unusable(tmp_path, monkeypatch):
    from models.registry import ConfigError
    from runner import load_config, run_task
    monkeypatch.setenv("ARGUS_SANDBOX_IMAGE", "python:3.13-slim")    # unpinned
    cfg = copy.deepcopy(load_config())
    cfg["impl"]["worker"] = "llm"
    cfg["roles"]["worker"]["model"] = "fake:scripted"
    cfg["sandbox"]["kind"] = "docker"
    with pytest.raises(ConfigError, match="sandbox"):
        run_task(goal="x", run_id="t", runs_dir=tmp_path, cfg=cfg, models={"worker": object()})


def test_image_is_part_of_the_tool_version(monkeypatch):
    monkeypatch.setenv("ARGUS_SANDBOX_IMAGE", "sha256:" + "a" * 64)
    v1 = sb.tool_version({"kind": "docker"})
    monkeypatch.setenv("ARGUS_SANDBOX_IMAGE", "sha256:" + "b" * 64)
    assert sb.tool_version({"kind": "docker"}) != v1


# ---- the worker uses it, and a committed RunPython step is never re-run ----------------------------

def test_worker_runs_python_once_and_replays_it_from_the_memo(cfg, tmp_path):
    from harness.llm import LLMCaller
    from harness.memo import Memo
    from models.fake import ScriptedChatModel, reply
    from nodes.contract import SALES_REPORT
    from nodes.llm_worker import make_llm_worker
    from runner import load_config
    from tools.registry import ToolGate
    import dataset

    truth = [list(x) for x in dataset.truth()["top3"]]
    code = ("import csv, collections, json\nt = collections.Counter()\n"
            "for r in csv.DictReader(open('/data/penjualan.csv')): t[r['product']] += int(r['omzet'])\n"
            "print(json.dumps([[k, v] for k, v in sorted(t.items(), key=lambda kv: -kv[1])[:3]]))")
    script = {"T2": [reply("", tool_calls=[{"name": "RunPython", "args": {"code": code}, "id": "p1"}]),
                     reply("", tool_calls=[{"name": "SubmitResult", "args": {"value": truth}, "id": "s1"}])]}
    c = copy.deepcopy(load_config())
    c["roles"]["worker"]["model"] = "fake:scripted"
    log = EventLog(tmp_path / "e.jsonl")
    model = ScriptedChatModel(script=script)
    fn = make_llm_worker(LLMCaller(c, "worker", log, model=model), SALES_REPORT,
                         ToolGate("worker", ["read_data", "run_python"], log), Memo(tmp_path / "m.sqlite"), log,
                         tokens=20_000, usd=1.0,
                         sandbox={"cfg": cfg, "workspace": str(tmp_path / "ws"), "data_dir": str(CSV_PATH.parent)})
    p = {"task": {"id": "T2", "output": "top3", "instruction": "Top 3 products by revenue.", "feedback": ""},
         "iteration": 0}
    out = fn(p)
    assert out["results"]["T2"]["value"] == truth
    tool_msg = model.calls[1]["messages"][-1]
    assert json.loads(json.loads(tool_msg.content)["stdout"]) == truth   # the sandbox computed the truth
    fn(p)                                                                # resume of the same node run
    runs = [e for e in log.read() if e["event"] == "sandbox_run"]
    assert len(runs) == 1 and len(model.calls) == 2                      # nothing re-run, nothing re-bought


def test_python_only_worker_reads_the_data_only_through_the_sandbox(cfg, tmp_path):
    # GPT review 2e: the directed live smoke gives workers RunPython and no ReadData. Offline first: the
    # prompt and tools say so, the value comes out of a real container, and read_data is never called.
    from harness.llm import LLMCaller
    from harness.memo import Memo
    from models.fake import ScriptedChatModel, reply
    from nodes.contract import SALES_REPORT
    from nodes.llm_worker import make_llm_worker
    from runner import load_config
    from tools.registry import ToolGate
    import dataset

    truth = [list(x) for x in dataset.truth()["trend"]]
    code = ("import csv, collections, json\nt = collections.Counter()\n"
            "for r in csv.DictReader(open('/data/penjualan.csv')): t[r['month']] += int(r['omzet'])\n"
            "print(json.dumps(sorted([k, v] for k, v in t.items())))")
    script = {"T3": [reply("", tool_calls=[{"name": "RunPython", "args": {"code": code}, "id": "p1"}]),
                     reply("", tool_calls=[{"name": "SubmitResult", "args": {"value": truth}, "id": "s1"}])]}
    c = copy.deepcopy(load_config())
    c["roles"]["worker"]["model"] = "fake:scripted"
    log = EventLog(tmp_path / "e.jsonl")
    model = ScriptedChatModel(script=script)
    fn = make_llm_worker(LLMCaller(c, "worker", log, model=model), SALES_REPORT,
                         ToolGate("worker", ["run_python"], log), Memo(tmp_path / "m.sqlite"), log,
                         tokens=20_000, usd=1.0,
                         sandbox={"cfg": cfg, "workspace": str(tmp_path / "ws"), "data_dir": str(CSV_PATH.parent)})
    p = {"task": {"id": "T3", "output": "trend", "instruction": "Monthly revenue trend.", "feedback": ""},
         "iteration": 0}
    out = fn(p)
    assert out["results"]["T3"]["value"] == truth
    assert [t.__name__ for t in model.bound_tools] == ["SubmitResult", "RunPython"]
    prompt = model.calls[0]["messages"][0].content
    assert "RunPython" in prompt and "/data/penjualan.csv" in prompt and "ReadData" not in prompt
    assert json.loads(json.loads(model.calls[1]["messages"][-1].content)["stdout"]) == truth
    evs = log.read()
    assert [e["tool"] for e in evs if e["event"] == "tool_call"] == ["run_python"]
    assert [e["exit_code"] for e in evs if e["event"] == "sandbox_run"] == [0]
