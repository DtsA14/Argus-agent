"""Mutants for the file-mode fix (tools/fs.py PathJail.write_text): each applied alone in a worktree; killed = a test failed (an error or a
skip is not a kill). Usage: fs_mode_mutants.py <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
F = "tools/fs.py"
TESTS = ["tests/test_fs_mode.py", "tests/test_fs.py"]
M = [
    ("the mode is never taken", F, "            mode = self._existing_mode(name, dfd)\n", "            mode = None\n"),
    ("the mode is never applied", F, "                    if mode is not None:\n                        os.fchmod(f.fileno(), mode)\n", ""),
    ("the mode is applied after the replace, by path", F, "                    if mode is not None:\n                        os.fchmod(f.fileno(), mode)\n                    os.fsync(f.fileno())",
     "                    os.fsync(f.fileno())"),
    ("special bits are carried over", F, "return stat.S_IMODE(st.st_mode) & 0o777 if", "return stat.S_IMODE(st.st_mode) if"),
    ("a new file gets another default", F, "O_NOFOLLOW, 0o644, dir_fd=dfd)", "O_NOFOLLOW, 0o666, dir_fd=dfd)"),
    ("every existing path counts as a file", F, "if stat.S_ISREG(st.st_mode) else None", "if True else None"),
    ("the mode of an executable is forced", F, "                        os.fchmod(f.fileno(), mode)", "                        os.fchmod(f.fileno(), 0o755)"),
    ("the mode is read from the wrong place", F, "st = os.stat(name, dir_fd=dfd, follow_symlinks=False)\n        except FileNotFoundError:\n            return None\n        return",
     "st = os.stat(tmp_dummy, dir_fd=dfd, follow_symlinks=False)\n        except FileNotFoundError:\n            return None\n        return"),
]

if __name__ == "__main__":
    killed = 0
    for name, f, old, new in M:
        p = WT / f
        orig = p.read_text()
        assert orig.count(old) == 1, (name, orig.count(old))
        p.write_text(orig.replace(old, new, 1))
        r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *TESTS], cwd=WT, capture_output=True, text=True)
        p.write_text(orig)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        k = "failed" in last
        killed += k
        fails = [line for line in r.stdout.splitlines() if line.startswith("FAILED")][:1]
        print(f"{'KILLED ' if k else 'SURVIVED'} {name}: {fails or last}", flush=True)
    print(f"RESULT: {killed}/{len(M)} killed")
