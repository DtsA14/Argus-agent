"""A pytest plugin for tests (not collected: its name does not start with test_): after conftest.py's own hook has run, write to
$GROUPLIST_OUT a JSON object {node id: whether the item is in the sandbox xdist group}. Used by test_xdist_groups.py and
test_verify_hardening.py with `-p grouplist_plugin --collect-only`."""
import json
import os


def pytest_collection_modifyitems(config, items):
    out = {it.nodeid: any(m.name == "xdist_group" and m.args == ("sandbox",) for m in it.iter_markers()) for it in items}
    with open(os.environ["GROUPLIST_OUT"], "w", encoding="utf-8") as f:
        json.dump(out, f)
