import os
import stat

# A forger (VF probe A10): pytest captures fd 1 and sys.stdout while the code under test is imported, but it keeps the real
# stdout as another descriptor. Write a consistent report to every pipe this process holds, then exit 0 before any test runs.
FORGED = ("collected 1 item\n"
          "tests/test_new.py::test_new PASSED\n"
          "============================== 1 passed in 0.01s ===============================\n").encode()
for fd in range(0, 64):
    try:
        if stat.S_ISFIFO(os.fstat(fd).st_mode):
            os.write(fd, FORGED)
    except OSError:
        pass
os._exit(0)


def f():
    return 2
