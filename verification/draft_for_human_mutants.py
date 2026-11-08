"""Mutants for SPEC_CONTROL_UI amendment 2 (for_human: the drafter's sentence for the human who approves): each alone;
killed = a test failed. Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
D, R, S, C = "acceptance/draft.py", "codetask/drafter.py", "router/stage_data.py", "config.yaml"
T = ["tests/test_draft.py", "tests/test_drafter.py", "tests/test_control_ui_d1.py"]
M = [
    ("not an optional key", D, 'OPTIONAL_KEYS = {"changed_tests", "for_human"}', 'OPTIONAL_KEYS = {"changed_tests"}', T),
    ("never checked", D, '    if "for_human" in d and (why := for_human_problem(d["for_human"])):',
     '    if False and (why := for_human_problem(d["for_human"])):', T),
    ("any type", D, '    if not isinstance(v, str) or not v.strip():', '    if not v or not str(v).strip():', T),
    ("blank accepted", D, '    if not isinstance(v, str) or not v.strip():', '    if not isinstance(v, str) or not v:', T),
    ("no length limit", D, "    if len(v) > FOR_HUMAN_MAX:", "    if False:", T),
    ("limit off by one", D, "FOR_HUMAN_MAX = 400", "FOR_HUMAN_MAX = 401", T),
    ("line breaks allowed", D, "    if any(ord(ch) < 32 or 127 <= ord(ch) < 160 for ch in v):",
     "    if any(ord(ch) < 10 or 127 <= ord(ch) < 160 for ch in v):", T),
    ("C1 allowed", D, "    if any(ord(ch) < 32 or 127 <= ord(ch) < 160 for ch in v):",
     "    if any(ord(ch) < 32 or ord(ch) == 127 for ch in v):", T),
    ("not a submit key", R, 'SUBMIT_KEYS = {"plan", "scope", "validation", "new_tests", "unverifiable", "budget_profile", "tools", "changed_tests",\n               "for_human"}',
     'SUBMIT_KEYS = {"plan", "scope", "validation", "new_tests", "unverifiable", "budget_profile", "tools", "changed_tests"}', T),
    ("dropped from the draft", R, '        draft["for_human"] = args["for_human"]', "        pass", T),
    ("taken when not asked", R, '        if not policy.get("for_human"):                # draft without it',
     '        if False:                # draft without it', T),
    ("not in the policy", R, '''                  **({"for_human": str(cfg["drafter"]["for_human_language"])}
                     if cfg["drafter"].get("for_human_language") else {}),''', "", T),
    ("not asked in the prompt", R, '''if policy.get("for_human") else []),''', "if False else []),", T),
    ("not in the review", R, '        if draft.get("for_human"):              # SPEC_CONTROL_UI', '        if False:              # SPEC_CONTROL_UI', T),
    ("not in the summary", S, '''            "for_human": _short(draft["for_human"], 500) if isinstance(draft.get("for_human"), str) else None}''',
     '''            "for_human": None}''', T),
    ("not cleaned", S, '''            "for_human": _short(draft["for_human"], 500) if''', '''            "for_human": draft["for_human"] if''', T),
    ("not in the config", C, "  for_human_language: Indonesian", "  for_human_language: null", T),
]
# Equivalent, not listed: the str() around the configured language (YAML gives a string).

if __name__ == "__main__":
    killed = 0
    for name, f, old, new, tests in M:
        p = WT / f
        orig = p.read_text()
        assert orig.count(old) == 1, (name, orig.count(old))
        p.write_text(orig.replace(old, new, 1))
        r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *tests], cwd=WT,
                           capture_output=True, text=True, timeout=300)
        p.write_text(orig)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        k = "failed" in last
        killed += k
        print(f"{'KILLED ' if k else 'SURVIVED'} {name}: {last}", flush=True)
    print(f"RESULT: {killed}/{len(M)} killed")
