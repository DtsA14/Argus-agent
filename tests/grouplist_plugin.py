"""A pytest plugin for tests (not collected: its name does not start with test_): after conftest.py's own hook has run, write to
$GROUPLIST_OUT a JSON object {node id: whether the item is in a sandbox xdist group} and, when $GROUPNAMES_OUT is set, to that file {node id: the group's name or null}. Used by test_xdist_groups.py and
test_verify_hardening.py with `-p grouplist_plugin --collect-only`."""
import json
import os


def pytest_collection_modifyitems(config, items):
    names = {it.nodeid: next((m.args[0] for m in it.iter_markers() if m.name == "xdist_group" and m.args), None) for it in items}
    with open(os.environ["GROUPLIST_OUT"], "w", encoding="utf-8") as f:
        json.dump({n: bool(g and g.startswith("sandbox")) for n, g in names.items()}, f)
    if os.environ.get("GROUPNAMES_OUT"):         # SPEC_SANDBOX_SPLIT: which sandbox group, not only whether
        with open(os.environ["GROUPNAMES_OUT"], "w", encoding="utf-8") as f:
            json.dump(names, f)
