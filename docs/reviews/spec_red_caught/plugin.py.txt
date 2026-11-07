import os, sys, json, pytest
M = sys.monitoring
TOOL = 4
ROOT = os.path.realpath(os.getcwd())
seen = {}        # node -> set of names of exceptions with a repo traceback caught by test code
cur = [None]

def is_repo(path):
    r = os.path.realpath(path) if os.path.isfile(path) else None
    return r is not None and r.startswith(ROOT + os.sep) and "site-packages" not in r and not os.path.basename(r).startswith("test_") and "/tests/" not in r

def is_test(path):
    r = os.path.realpath(path) if os.path.isfile(path) else None
    return r is not None and r.startswith(ROOT + os.sep) and not is_repo(path)

def handled(code, offset, exc):
    if cur[0] is None or not is_test(code.co_filename):
        return
    tb, repo = exc.__traceback__, False
    while tb is not None:
        if is_repo(tb.tb_frame.f_code.co_filename):
            repo = True
        tb = tb.tb_next
    if repo:
        seen.setdefault(cur[0], set()).update(c.__name__ for c in type(exc).__mro__ if c is not object)

def pytest_sessionstart(session):
    M.use_tool_id(TOOL, "argus-red")
    M.register_callback(TOOL, M.events.EXCEPTION_HANDLED, handled)
    M.set_events(TOOL, M.events.EXCEPTION_HANDLED)

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    cur[0] = item.nodeid
    yield
    cur[0] = None

def pytest_sessionfinish(session):
    print("\nRAISED_CAUGHT_BY_TEST " + json.dumps({k.split("::")[1]: sorted(v) for k, v in seen.items()}, indent=1))
