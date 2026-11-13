"""Candidate issues for the second outside batch (read only, GitHub metadata only: no model, no maintainer test or fix is read).
Rule, fixed before the run (PREFLIGHT.md of this directory), changed from pilots/outside_v0 by what batch 1 taught:
  1. an issue closed by a MERGED pull request of the same repository, closed on or after 2025-11-12, not one of batch 1's ten;
  2. the fix changes at least one test file and one source file (docs excluded), the source diff is at most 150 lines, the issue body is at
     most 8,000 characters, and the fix touches no dependency or build configuration;
  3. one issue per fix PR (several issues closed by one PR: the newest closed is kept);
  4. the base is the PARENT OF THE FIRST COMMIT of the pull request (not of the merge commit: a rebase-merged series made batch 1's #343 start
     from code that already had its fix); the issue text is the issue's title and body, byte for byte.
usage: preflight_scan.py <repo>...   -> prints one JSON object per eligible candidate, newest first"""
import json
import re
import subprocess
import sys

V0 = {("mahmoud/boltons", n) for n in (480, 439, 261, 343, 383)} | {("more-itertools/more-itertools", n) for n in (1344, 1308, 1304, 1293, 1275)}
TESTPAT = re.compile(r"(^|/)(tests?|testing)/|(^|/)test_[^/]*\.py$|_test\.py$|(^|/)conftest\.py$")
DEPFILES = ("pyproject.toml", "setup.py", "setup.cfg", "requirements", "tox.ini")
QUERY = """query($o:String!,$n:String!,$c:String){repository(owner:$o,name:$n){issues(states:CLOSED,first:50,after:$c,orderBy:{field:UPDATED_AT,direction:DESC}){
pageInfo{hasNextPage endCursor}nodes{number title body closedAt closedByPullRequestsReferences(first:3,includeClosedPrs:false){nodes{number merged mergedAt
mergeCommit{oid} baseRepository{nameWithOwner}}}}}}}"""


def gh(*a):
    r = subprocess.run(["gh", *a], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr[:200])
    return r.stdout


def run(repo, pages=8):
    owner, name = repo.split("/")
    cands, cur = [], None
    for _ in range(pages):
        args = ["api", "graphql", "-f", "query=" + QUERY, "-F", "o=" + owner, "-F", "n=" + name] + (["-F", "c=" + cur] if cur else [])
        d = json.loads(gh(*args))["data"]["repository"]["issues"]
        for i in d["nodes"]:
            prs = [p for p in i["closedByPullRequestsReferences"]["nodes"] if p["merged"] and p["baseRepository"]["nameWithOwner"] == repo and p["mergeCommit"]]
            if prs and i["closedAt"] >= "2025-11-12" and (repo, i["number"]) not in V0:
                cands.append((i, prs[0]))
        if not d["pageInfo"]["hasNextPage"]:
            break
        cur = d["pageInfo"]["endCursor"]
    cands.sort(key=lambda t: t[0]["closedAt"], reverse=True)
    out, used_prs = [], set()
    for i, p in cands:
        if p["number"] in used_prs:
            continue                                                        # one issue per fix PR: the newest closed was kept
        used_prs.add(p["number"])
        files = json.loads(gh("api", f"repos/{repo}/pulls/{p['number']}/files", "--paginate"))
        tests = [f for f in files if TESTPAT.search(f["filename"])]
        non = [f for f in files if not TESTPAT.search(f["filename"]) and not f["filename"].endswith((".md", ".rst", ".txt"))]
        nondiff = sum(f["additions"] + f["deletions"] for f in non)
        deps = any(any(x in f["filename"] for x in DEPFILES) for f in files)
        if not tests or not non or len(i["body"] or "") > 8000 or nondiff > 150 or deps:
            continue
        commits = json.loads(gh("api", f"repos/{repo}/pulls/{p['number']}/commits", "--paginate"))
        first = commits[0]
        base = first["parents"][0]["sha"] if first.get("parents") else None
        out.append({"repo": repo, "issue": i["number"], "title": i["title"][:100], "closed": i["closedAt"][:10], "pr": p["number"],
                    "merge": p["mergeCommit"]["oid"], "first_commit": first["sha"][:12], "base": base, "pr_commits": len(commits),
                    "test_files": [f["filename"] for f in tests], "non_test_diff": nondiff, "body_chars": len(i["body"] or "")})
    return out


if __name__ == "__main__":
    for repo in sys.argv[1:]:
        for row in run(repo):
            print(json.dumps(row))
