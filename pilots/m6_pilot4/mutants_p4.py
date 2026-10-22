"""Mutation check for M6 pilot 4: wrong versions of is_peak, each applied on top of the reference patch in its own git worktree of the
base commit (4 at a time); tests/test_peak_window.py must fail for every one. Run from a checkout of the repository (VM)."""
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PY = sys.executable
ROOT = Path.cwd()
BASE = "983a4ee"
PATCH = ROOT / "pilots/m6_pilot4/reference.patch"
TEST = ROOT / "pilots/m6_pilot4/new_test.txt"
PR = "models/pricing.py"
COND = 'start <= now.hour < end if start <= end else (now.hour >= start or now.hour < end)'

M = [
    ("wrap_uses_and_instead_of_or", [(PR, "(now.hour >= start or now.hour < end)", "(now.hour >= start and now.hour < end)")]),
    ("wrap_end_inclusive", [(PR, "or now.hour < end)", "or now.hour <= end)")]),
    ("wrap_start_exclusive", [(PR, "(now.hour >= start or", "(now.hour > start or")]),
    ("equal_start_end_is_all_day", [(PR, COND, 'start <= now.hour < end if start < end else (now.hour >= start or now.hour < end)')]),
    ("ordinary_end_inclusive", [(PR, COND, 'start <= now.hour <= end if start <= end else (now.hour >= start or now.hour < end)')]),
    ("ordinary_start_exclusive", [(PR, COND, 'start < now.hour < end if start <= end else (now.hour >= start or now.hour < end)')]),
    ("weekday_on_the_date_the_window_began", [(PR, 'now.weekday() >= 5:', '(now - __import__("datetime").timedelta(hours=4)).weekday() >= 5:')]),
    ("weekend_check_inverted", [(PR, 'now.weekday() >= 5:', 'now.weekday() < 5:')]),
    ("weekdays_only_ignored", [(PR, 'now.weekday() >= 5:', 'now.weekday() >= 7:')]),
    ("other_zone_not_converted_to_utc", [(PR, "    now = now.astimezone(timezone.utc)\n", "")]),
    ("all_windows_must_match", [(PR, "return any(", "return all(")]),
    ("empty_dict_not_handled", [(PR, "if not window:", "if window is None:")]),
    ("crossing_windows_never_match_again", [(PR, COND, 'start <= now.hour < end')]),
    ("crossing_window_matches_only_the_evening", [(PR, "(now.hour >= start or now.hour < end)", "(now.hour >= start)")]),
    ("crossing_window_matches_only_the_morning", [(PR, "(now.hour >= start or now.hour < end)", "(now.hour < end)")]),
    ("window_with_end_24_dropped", [(PR, COND, '(start <= now.hour < end if start <= end else (now.hour >= start or now.hour < end)) and end < 24')]),
]


def run(item):
    name, edits = item
    wt = ROOT.parent / f"p4mut_{name}"
    subprocess.run(["git", "worktree", "add", "-q", "--detach", str(wt), BASE], cwd=ROOT, check=True)
    try:
        for f in (".sandbox_image", ".sandbox_image_argus"):
            if (ROOT / f).exists():
                shutil.copy(ROOT / f, wt / f)
        subprocess.run(["git", "apply", str(PATCH)], cwd=wt, check=True)
        shutil.copy(TEST, wt / "tests" / "test_peak_window.py")
        for f, old, new in edits:
            text = (wt / f).read_text(encoding="utf-8")
            assert text.count(old) == 1, f"{name}: {old[:60]!r} found {text.count(old)} times"
            (wt / f).write_text(text.replace(old, new), encoding="utf-8")
        r = subprocess.run([PY, "-m", "pytest", "tests/test_peak_window.py", "-q", "-p", "no:cacheprovider"],
                           cwd=wt, capture_output=True, text=True, timeout=600)
        last = [l for l in r.stdout.splitlines() if l.startswith("FAILED")][:1]
        return name, r.returncode == 1, (last[0][:150] if last else r.stdout.strip().splitlines()[-1][:150])
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(wt)], cwd=ROOT)


with ThreadPoolExecutor(4) as pool:
    results = []
    for name, dead, why in pool.map(run, M):
        results.append(dead)
        print(f"{'KILLED  ' if dead else 'SURVIVED'} {name}: {why}", flush=True)
print(f"{sum(results)}/{len(M)} mutants killed")
sys.exit(0 if all(results) else 1)
