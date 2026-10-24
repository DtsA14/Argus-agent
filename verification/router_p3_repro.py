"""Router pilot #3, after the agent's patch: check_against_repo with real git (no FakeGit)."""
import hashlib, shutil, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from acceptance import intake
t = Path(tempfile.mkdtemp()); repo = t / "r"; (repo / "pkg").mkdir(parents=True); (repo / "tests").mkdir()
(repo / "pkg" / "m.py").write_text("X = 1\n")
old = b"def test_old():\n    assert 1 == 1\n"; (repo / "tests" / "test_old.py").write_bytes(old)
g = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True)
g("init", "-q"); g("add", "-A"); g("-c", "user.name=a", "-c", "user.email=a@b", "commit", "-qm", "b")
root = t / "root"; rec = intake.intake(repo, "HEAD", "base", root=root)
base = root / "fixtures" / "repos" / "base"
sha = lambda b: hashlib.sha256(b).hexdigest()
new, changed = b"def test_x():\n    assert True\n", b"def test_old():\n    assert 2 == 2\n"

def task_ws(name, edit=None):
    ws = root / "fixtures" / "repos" / name; shutil.copytree(base, ws)
    (ws / "tests" / "test_x.py").write_bytes(new); (ws / "tests" / "test_old.py").write_bytes(changed)
    if edit: edit(ws)
    return ws
task = dict(rec, kind="task", name="task", added={"tests/test_x.py": sha(new)},
            changed={"tests/test_old.py": {"before": sha(old), "after": sha(changed), "removed": [], "modified": []}})
cases = [
    ("intake record, its own snapshot", rec, base, "[]"),
    ("task record, exactly as approved", task, task_ws("ok"), "[]"),
    ("task record, another file changed", task, task_ws("mod", lambda w: (w / "pkg" / "m.py").write_text("X = 2\n")), "mismatch"),
    ("task record, an extra file", task, task_ws("add", lambda w: (w / "pkg" / "extra.py").write_text("")), "mismatch"),
    ("task record, an approved test edited", task, task_ws("edt", lambda w: (w / "tests" / "test_x.py").write_bytes(b"x")), "mismatch"),
    ("task record, a changed test back to before", task, task_ws("bef", lambda w: (w / "tests" / "test_old.py").write_bytes(old)), "mismatch"),
    ("intake record on a task workspace", rec, task_ws("plain"), "mismatch"),
]
bad = 0
for name, r, ws, want in cases:
    got = intake.check_against_repo(r, ws, repo)
    ok = (got == []) == (want == "[]")
    bad += not ok
    print(f"{'ok ' if ok else 'BAD'} {name}: {got}")
print("RESULT:", "ok" if not bad else f"{bad} unexpected")
