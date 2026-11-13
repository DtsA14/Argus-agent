"""Containers of one test, not of the machine (SPEC_VERIFY_HARDENING). A test that looks for, or removes, sandbox containers gives
its own run a token as the label `argus.test=<token>` (tools/sandbox.py `labels`) and asks only for that label: a live job or a
second verify on the same VM has containers with the label `argus.sandbox=1` too, and must neither fail the check nor lose its
container to a cleanup. Not collected: the name does not start with test_."""
import subprocess
import uuid


def new_token():
    return uuid.uuid4().hex[:12]


def labels(token):
    return {"argus.test": token}


def ids(token, all_states=False):
    """The ids of this token's sandbox containers: running ones, or all (also stopped) with all_states."""
    r = subprocess.run(["docker", "ps", "-aq" if all_states else "-q", "--filter", "label=argus.sandbox=1",
                        "--filter", f"label=argus.test={token}"], capture_output=True, text=True)
    return r.stdout.split()


def remove(token):
    """Force-remove this token's containers (and no other); returns their ids."""
    found = ids(token, all_states=True)
    if found:
        subprocess.run(["docker", "rm", "-f", *found], capture_output=True)
    return found
