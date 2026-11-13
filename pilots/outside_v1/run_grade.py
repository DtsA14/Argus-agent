import json, os, subprocess, glob, re
S = "/tmp/claude-1001/-home-ubuntu-Argus-agent/d9ea9397-ab6c-4d6a-80b5-e6acfdb0d7df/scratchpad"
J = "/home/ubuntu/Argus-agent/jobs"
repos = {"boltons": "mahmoud/boltons", "more-itertools": "more-itertools/more-itertools"}
cands = {(json.loads(l)["repo"].split("/")[1], json.loads(l)["issue"]): json.loads(l) for l in open(S + "/cands.jsonl")}
names = json.load(open(S + "/pr_test_names.json"))
jobs = [  # label, repo, issue, pr, job, base, new?
    ("mi-1284", "more-itertools", 1284, 1285, "j20261113_011018_89e5", None, True),
    ("mi-1277", "more-itertools", 1277, 1278, "j20261113_012156_3af4", None, True),
    ("mi-1257", "more-itertools", 1257, 1261, "j20261113_012640_fa75", None, True),
    ("bo-393", "boltons", 393, 394, "j20261113_013152_6552", None, True),
    ("bo-322", "boltons", 322, 388, "j20261113_014406_c297", None, True),
    ("mi-1304c", "more-itertools", 1304, 1305, "j20261113_014810_75fb", "790bb0bb2c03e7a07282e5f16f4b1fde35b8fcf5", False),
    ("mi-1344c", "more-itertools", 1344, 1345, "j20261113_015507_ddab", "08dca284ba5446a026afdc34067b658f9da989eb", False),
    ("bo-383c", "boltons", 383, 416, "j20261113_020714_71a4", "ebc7a8f776debfa33f0b380b57a444bca75a251b", False),
]
res = {}
for label, repo, issue, pr, job, base, new in jobs:
    r = repos[repo]
    merge = subprocess.run(["gh", "api", f"repos/{r}/pulls/{pr}", "-q", ".merge_commit_sha"], capture_output=True, text=True).stdout.strip()
    if new:
        base = cands[(repo, issue)]["base"]
    files = json.loads(subprocess.run(["gh", "api", f"repos/{r}/pulls/{pr}/files", "--paginate"], capture_output=True, text=True).stdout)
    tfiles = [f["filename"] for f in files if re.match(r"(tests?/)", f["filename"]) and f["filename"].endswith(".py")]
    patch = sorted(glob.glob(f"{J}/{job}/runs/{job}-a*/review/changes.patch"))[-1]
    env = {**os.environ, "GRADE_FILES": ",".join(tfiles)}
    if new:
        env["GRADE_NAMES"] = ",".join(names[f"{repo}#{pr}"])
    script = "grade_b2_ut.py" if repo == "more-itertools" else "grade_b2_pytest.py"
    subprocess.run(["git", "-C", os.path.expanduser(f"~/outside/{repo}"), "fetch", "-q", "origin"])
    p = subprocess.run(["python3", f"{S}/{script}", label, os.path.expanduser(f"~/outside/{repo}"), base, merge, patch], capture_output=True, text=True, env=env)
    open(f"{S}/b2/{label}.grade.txt", "w").write(p.stdout + p.stderr)
    print(label, "|", " | ".join(l for l in p.stdout.splitlines() if l.startswith(("fix:", "FAIL_TO", "argus", "RESOLVED", "NOT RES", "ARGUS", "FIX variant"))), flush=True)
