"""Mutation check for M6 pilot 5: wrong versions of the strict is_peak, each applied on top of the reference patch in its own git worktree of the
base commit (4 at a time); tests/test_peak_window_strict.py (and the existing tests/test_peak_window.py) must fail for every one."""
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PY = sys.executable
ROOT = Path.cwd()
BASE = "716d1dd"
PATCH = ROOT / "pilots/m6_pilot5/reference.patch"
TEST = ROOT / "pilots/m6_pilot5/new_test.txt"
PR = "models/pricing.py"
DICT_CHECK = '    if not isinstance(window, dict):\n        raise WindowError(f"a peak window must be a dict, got {window!r}")\n'
KEY_CHECK = '    if "utc_hours" not in window:\n        raise WindowError(f"a peak window needs \'utc_hours\', got {window!r}")\n'
HOURS_CHECK = ('    if not isinstance(hours, (list, tuple)):\n'
               '        raise WindowError(f"\'utc_hours\' must be a list of [start, end] pairs, got {hours!r}")\n')
RANGE = ('        if not (0 <= start <= 23 and 0 <= end <= 24):\n'
         '            raise WindowError(f"\'utc_hours\' item {item!r} is out of range: start must be 0..23 and end 0..24")\n')
FLAG = ('    if "weekdays_only" in window and type(window["weekdays_only"]) is not bool:\n'
        '        raise WindowError(f"\'weekdays_only\' must be true or false, got {window[\'weekdays_only\']!r}")\n')
NAIVE = ('    if now.tzinfo is None or now.utcoffset() is None:\n'
         '        raise WindowError(f"\'now\' must be a timezone-aware datetime, got a naive one: {now!r}")\n')
ITEM = 'if not (isinstance(item, (list, tuple)) and len(item) == 2 and all(type(x) is int for x in item)):'
MULT = '    return price.get("peak_multiplier", 1) if (price and is_peak(window, now)) else 1\n'
COST = '    multiplier = price.get("peak_multiplier", 1) if is_peak(window, now) else 1\n'

M = [
    ("v1_no_dict_check", [(PR, DICT_CHECK, "")]),
    ("v2_missing_key_not_checked", [(PR, KEY_CHECK, "")]),
    ("v2_missing_key_is_empty_hours", [(PR, KEY_CHECK, ""), (PR, '    hours = window["utc_hours"]\n', '    hours = window.get("utc_hours") or []\n'),
                                       (PR, '    for start, end in window["utc_hours"]:', '    for start, end in window.get("utc_hours") or []:')]),
    ("v3_hours_type_not_checked", [(PR, HOURS_CHECK, "")]),
    ("v4_bool_accepted", [(PR, "type(x) is int", "isinstance(x, int)")]),
    ("v4_float_accepted", [(PR, "type(x) is int", "isinstance(x, (int, float))")]),
    ("v4_length_not_checked", [(PR, " and len(item) == 2", "")]),
    ("v4_items_not_checked", [(PR, ITEM, "if False:")]),
    ("v5_start_up_to_24", [(PR, "0 <= start <= 23", "0 <= start <= 24")]),
    ("v5_end_up_to_25", [(PR, "0 <= end <= 24", "0 <= end <= 25")]),
    ("v5_negative_start_accepted", [(PR, "0 <= start <= 23", "-1 <= start <= 23")]),
    ("v5_range_not_checked", [(PR, RANGE, "")]),
    ("v5_end_24_refused", [(PR, "0 <= end <= 24", "0 <= end <= 23")]),
    ("v6_flag_not_checked", [(PR, FLAG, "")]),
    ("v6_none_flag_accepted", [(PR, 'type(window["weekdays_only"]) is not bool', 'type(window["weekdays_only"]) not in (bool, type(None))')]),
    ("v7_naive_not_checked", [(PR, NAIVE, "")]),
    ("v7_naive_checked_for_empty_window_too", [(PR, "    if not window:\n        return False\n    _checked(window)\n",
                                                "    if now.tzinfo is None:\n        raise WindowError('naive')\n    if not window:\n        return False\n    _checked(window)\n")]),
    ("whole_window_not_checked_before_the_hours", [(PR, "    _checked(window)\n", ""),
                                                   (PR, '    for start, end in window["utc_hours"]:\n',
                                                    '    for start, end in window["utc_hours"]:\n        _checked({"utc_hours": [[start, end]]})\n')]),
    ("empty_hours_refused", [(PR, "    for item in hours:\n", "    if not hours:\n        raise WindowError('empty')\n    for item in hours:\n")]),
    ("start_equals_end_refused", [(PR, "        start, end = item\n", "        start, end = item\n        if start == end:\n            raise WindowError('empty window')\n")]),
    ("falsy_window_checked", [(PR, "    if not window:\n        return False\n", "    if window is None:\n        return False\n")]),
    ("message_does_not_show_the_value", [(PR, 'f"a peak window must be a dict, got {window!r}"', '"a peak window must be a dict"')]),
    ("error_is_not_a_value_error", [(PR, "class WindowError(ValueError):", "class WindowError(Exception):")]),
    ("zone_replaced_not_converted", [(PR, "now = now.astimezone(timezone.utc)", "now = now.replace(tzinfo=timezone.utc)")]),
    ("multiplier_swallows_the_error", [(PR, MULT, "    try:\n    " + MULT + "    except WindowError:\n        return 1\n")]),
    ("cost_usd_swallows_the_error", [(PR, COST, "    try:\n    " + COST + "    except WindowError:\n        multiplier = 1\n")]),
    ("across_midnight_broken", [(PR, "if hour >= start or hour < end:", "if hour >= start and hour < end:")]),
    ("end_inclusive", [(PR, "if start <= hour < end:", "if start <= hour <= end:")]),
    ("weekend_check_dropped", [(PR, '    if window.get("weekdays_only") and now.weekday() >= 5:\n        return False\n', "")]),
]


def run(item):
    name, edits = item
    wt = ROOT.parent / f"p5mut_{name}"
    subprocess.run(["git", "worktree", "add", "-q", "--detach", str(wt), BASE], cwd=ROOT, check=True)
    try:
        for f in (".sandbox_image", ".sandbox_image_argus"):
            if (ROOT / f).exists():
                shutil.copy(ROOT / f, wt / f)
        subprocess.run(["git", "apply", str(PATCH)], cwd=wt, check=True)
        shutil.copy(TEST, wt / "tests" / "test_peak_window_strict.py")
        for f, old, new in edits:
            text = (wt / f).read_text(encoding="utf-8")
            assert text.count(old) == 1, f"{name}: {old[:70]!r} found {text.count(old)} times"
            (wt / f).write_text(text.replace(old, new), encoding="utf-8")
        r = subprocess.run([PY, "-m", "pytest", "tests/test_peak_window_strict.py", "tests/test_peak_window.py", "-q", "-p", "no:cacheprovider"],
                           cwd=wt, capture_output=True, text=True, timeout=600)
        last = [line for line in r.stdout.splitlines() if line.startswith("FAILED")][:1]
        return name, r.returncode == 1, (last[0][:140] if last else r.stdout.strip().splitlines()[-1][:140])
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(wt)], cwd=ROOT)


with ThreadPoolExecutor(4) as pool:
    results = []
    for name, dead, why in pool.map(run, M):
        results.append(dead)
        print(f"{'KILLED  ' if dead else 'SURVIVED'} {name}: {why}", flush=True)
print(f"{sum(results)}/{len(M)} mutants killed")
sys.exit(0 if all(results) else 1)
