import pytest
from lib import mod

def test_t1_true_swallow():            # exception from repo code, caught by the test, traceback lost
    err = None
    try:
        mod.strict(-1)
    except ValueError as e:
        err = e
    pytest.fail(f"strict failed with ValueError: {err}")           # outside the except: no __context__

def test_t2_expects_exception():       # nothing raised at all: the old code does not raise
    mod.tolerant(1)
    pytest.fail("tolerant must raise ValueError for 1")

def test_t3_callsite_typeerror():      # unknown kwarg: TypeError raised at the call site, no repo frame
    err = None
    try:
        mod.plain(1, z=2)
    except TypeError as e:
        err = e
    pytest.fail(f"plain raised TypeError: {err}")

def test_t4_c_raised_in_repo_base_name():   # KeyError raised in repo by a C operation; message names the base class
    err = None
    try:
        mod.lookup({})
    except LookupError as e:
        err = e
    pytest.fail(f"lookup raised LookupError {err!r}")

def test_t5_repo_handles_internally():  # ValueError raised and caught inside repo; message mentions it as expectation
    mod.tolerant(1)
    pytest.fail("tolerant must raise ValueError")
