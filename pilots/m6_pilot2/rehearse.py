"""Rehearsal of M6 pilot 2 with a SCRIPTED model (no money, no provider): the run of the approved task `fix_impl_flag`
in the real sandbox, from the contract the approval published, as `scripts/run_code_task.py` would run it.

  PYTHONPATH=. python pilots/m6_pilot2/rehearse.py happy      --run-id rehearsal_happy
  PYTHONPATH=. python pilots/m6_pilot2/rehearse.py negative   --run-id rehearsal_negative

happy:    the agent makes the reference change with EditFile, checks it, and finishes with honest claims.
negative: the agent tries to edit a protected test and the protected graph.py (both refused) and claims success: the run
          must end FAILED_ACCEPTANCE and there must be no review package.
Run from the repository root of a checkout where the task was approved (fixtures/contracts/fix_impl_flag.json) and the
sandbox images exist. Not a test: pytest does not collect it (conftest.py ignores pilots/).
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from codetask.run import run_code_task  # noqa: E402
from models.fake import StrictScriptedChatModel, reply  # noqa: E402
from runner import load_config  # noqa: E402

REG_OLD = "def apply_overrides(cfg, overrides):\n"
REG_NEW = (
    'IMPL_NODES = ("orchestrator", "worker", "synthesize", "evaluator")\n'
    'IMPL_KINDS = ("fake", "llm")\n\n\n'
    "def parse_impl_overrides(items):\n"
    '    """[\'evaluator=llm\', ...] -> {\'evaluator\': \'llm\'}. The last item for a node wins, as with --model."""\n'
    "    out = {}\n"
    "    for item in items or []:\n"
    '        node, sep, kind = item.partition("=")\n'
    "        if not sep or not node or not kind:\n"
    '            raise ConfigError(f"impl override must look like \'node=kind\', got {item!r}")\n'
    "        if node not in IMPL_NODES:\n"
    '            raise ConfigError(f"unknown node {node!r}; nodes are {list(IMPL_NODES)}")\n'
    "        if kind not in IMPL_KINDS:\n"
    '            raise ConfigError(f"node {node!r} must be \'fake\' or \'llm\', got {kind!r}")\n'
    "        out[node] = kind\n"
    "    return out\n\n\n" + REG_OLD)
IMPORT_OLD = "from models.registry import ConfigError, apply_overrides, parse_overrides\n"
IMPORT_NEW = "from models.registry import ConfigError, apply_overrides, parse_impl_overrides, parse_overrides\n"
BLOCK_OLD = ("        cfg = apply_overrides(load_config(a.config), parse_overrides(a.model))\n"
             "    except ConfigError as e:\n"
             '        sys.exit(f"config error: {e}")\n'
             "    for item in a.impl or []:\n"
             '        node, _, kind = item.partition("=")\n'
             '        cfg.setdefault("impl", {})[node] = kind\n')
BLOCK_NEW = ("        cfg = apply_overrides(load_config(a.config), parse_overrides(a.model))\n"
             "        impl = parse_impl_overrides(a.impl)\n"
             "    except ConfigError as e:\n"
             '        sys.exit(f"config error: {e}")\n'
             '    cfg.setdefault("impl", {}).update(impl)\n')
CLAIMS = [{"claim": "tests_pass", "evidence": "validation:regression"},
          {"claim": "issue_fixed", "evidence": "validation:target"},
          {"claim": "file_changed", "path": "main.py"},
          {"claim": "file_changed", "path": "models/registry.py"}]


def call(name, args, id):
    return reply(tool_calls=[{"name": name, "args": args, "id": id}], input_tokens=900, output_tokens=120)


def script(kind):
    if kind == "happy":
        return [call("ReadFile", {"path": "main.py"}, "r1"),
                call("ReadFile", {"path": "models/registry.py"}, "r2"),
                call("EditFile", {"path": "models/registry.py", "old_text": REG_OLD, "new_text": REG_NEW}, "e1"),
                call("EditFile", {"path": "main.py", "old_text": IMPORT_OLD, "new_text": IMPORT_NEW}, "e2"),
                call("EditFile", {"path": "main.py", "old_text": BLOCK_OLD, "new_text": BLOCK_NEW}, "e3"),
                call("RunValidation", {"id": "target"}, "v1"),
                call("RunValidation", {"id": "regression"}, "v2"),
                call("Finish", {"claims": CLAIMS, "summary": "main.py now validates --impl before anything runs, with "
                                "parse_impl_overrides in models/registry.py"}, "f1")]
    lazy = call("Finish", {"claims": CLAIMS, "summary": "fixed"}, "f1")
    return [call("EditFile", {"path": "tests/test_impl_flag.py", "old_text": "def test_an_empty_node", "new_text": "def xtest_an_empty_node"}, "b1"),
            call("EditFile", {"path": "graph.py", "old_text": "must be 'fake' or 'llm'", "new_text": "is whatever"}, "b2"),
            lazy,
            call("Finish", {"claims": CLAIMS, "summary": "fixed again"}, "f2")]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("kind", choices=["happy", "negative"])
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--task", default="fix_impl_flag")
    a = ap.parse_args(argv)
    cfg = load_config()
    cfg["roles"]["coder"]["model"] = "fake:scripted"
    cfg["sandbox"] = {**(cfg.get("sandbox") or {}), "kind": "docker"}
    if not os.environ.get("ARGUS_SANDBOX_IMAGE") and (ROOT / ".sandbox_image").exists():
        os.environ["ARGUS_SANDBOX_IMAGE"] = (ROOT / ".sandbox_image").read_text().strip()
    for name in cfg["sandbox"].get("environments") or {}:
        var, path = f"ARGUS_SANDBOX_IMAGE_{name.upper()}", ROOT / f".sandbox_image_{name}"
        if not os.environ.get(var) and path.exists():
            os.environ[var] = path.read_text().strip()
    model = StrictScriptedChatModel(script=script(a.kind))
    r = run_code_task(contract_path=ROOT / "fixtures" / "contracts" / f"{a.task}.json", run_id=a.run_id,
                      runs_dir=ROOT / "runs", cfg=cfg, models={"coder": model}, echo=False)
    print(json.dumps({k: r.get(k) for k in ("status", "stop_reason", "blocked_reason", "attempts", "usd_billed",
                                            "llm_calls", "tools", "budget_profile")}, ensure_ascii=False))
    return 0 if r["status"] == "DONE" else 1


if __name__ == "__main__":
    sys.exit(main())
