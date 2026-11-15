import json, os, sys, contextlib, io
import pytest
nonce, targets = sys.argv[1], sys.argv[2:]
FIXED = ["-p", "no:cacheprovider", "-o", "addopts=", "-o", "console_output_style=classic", "--rootdir", os.getcwd(), "-v", "--tb=short", "--color=no", "-rN"]
class Rec:
    def __init__(self): self.out = {}
    def pytest_runtest_logreport(self, report):
        if report.when == "call" or report.outcome != "passed":
            self.out[report.nodeid] = report.outcome
r1 = Rec()
rc1 = int(pytest.main([*FIXED, *targets], plugins=[r1]))
tag = os.urandom(8).hex()
d = f"/tmp/argus_canary_{tag}"; os.makedirs(d)
p = f"{d}/test_argus_canary_{tag}.py"
open(p, "w").write(f"def test_pass_{tag}(): assert 1 == 1\ndef test_fail_{tag}(): assert 1 == 2\ndef test_error_{tag}(): raise RuntimeError('{tag}')\n")
r2 = Rec()
with contextlib.redirect_stdout(io.StringIO()):
    rc2 = int(pytest.main(["-p", "no:cacheprovider", "-o", "addopts=", "--rootdir", d, "-q", "--tb=no", "--color=no", p], plugins=[r2]))
canary = {k.split("::")[-1].rsplit("_", 1)[0]: v for k, v in r2.out.items()}
sys.stdout.write("\n" + nonce + json.dumps({"rc": rc1, "outcomes": r1.out, "canary": canary, "canary_rc": rc2}, sort_keys=True) + "\n")
sys.stdout.flush(); sys.exit(rc1)
