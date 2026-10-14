"""Phase 2d: the Docker sandbox, tested in a real container.

These tests check the *effect* of every hardening flag from inside the container, not just that the
flag was passed. They need Docker and a pinned image (ARGUS_SANDBOX_IMAGE or sandbox.image). Without
them they are skipped with "SANDBOX NOT AVAILABLE", and scripts/verify.sh then FAILS unless
ARGUS_SANDBOX_OPTIONAL=1: a skipped sandbox test does not count as passing.
"""
import copy
import json
import subprocess
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


def test_output_is_capped(cfg, tmp_path):
    r = run(cfg, "print('x' * 100000)", tmp_path)
    assert r["truncated"] and len(r["stdout"].encode()) <= 4096


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
