import json, subprocess, sys, re
def gh(*a):
    r=subprocess.run(["gh",*a],capture_output=True,text=True)
    if r.returncode: raise RuntimeError(r.stderr[:200])
    return r.stdout
TESTPAT=re.compile(r"(^|/)(tests?|testing)/|(^|/)test_[^/]*\.py$|_test\.py$|(^|/)conftest\.py$")
DEPFILES=("pyproject.toml","setup.py","setup.cfg","requirements","tox.ini")
def run(repo, want=12):
    owner,name=repo.split("/")
    q='''query($o:String!,$n:String!,$c:String){repository(owner:$o,name:$n){issues(states:CLOSED,first:50,after:$c,orderBy:{field:UPDATED_AT,direction:DESC}){pageInfo{hasNextPage endCursor}nodes{number title body closedAt closedByPullRequestsReferences(first:3,includeClosedPrs:false){nodes{number merged mergedAt mergeCommit{oid} baseRepository{nameWithOwner}}}}}}}'''
    out=[]; cur=None; seen=0
    while len(out)<want*4 and seen<6:
        args=["api","graphql","-f","query="+q,"-F","o="+owner,"-F","n="+name]
        if cur: args+=["-F","c="+cur]
        d=json.loads(gh(*args))["data"]["repository"]["issues"]
        for i in d["nodes"]:
            prs=[p for p in i["closedByPullRequestsReferences"]["nodes"] if p["merged"] and p["baseRepository"]["nameWithOwner"]==repo and p["mergeCommit"]]
            if not prs: continue
            out.append((i,prs[0]))
        if not d["pageInfo"]["hasNextPage"]: break
        cur=d["pageInfo"]["endCursor"]; seen+=1
    out.sort(key=lambda t:t[0]["closedAt"], reverse=True)
    rows=[]
    for i,p in out:
        if i["closedAt"]<"2025-11-11": continue
        files=json.loads(gh("api",f"repos/{repo}/pulls/{p['number']}/files","--paginate"))
        tests=[f for f in files if TESTPAT.search(f["filename"])]
        non=[f for f in files if not TESTPAT.search(f["filename"]) and not f["filename"].endswith((".md",".rst",".txt"))]
        nondiff=sum(f["additions"]+f["deletions"] for f in non)
        deps=any(any(d in f["filename"] for d in DEPFILES) for f in files)
        parent=json.loads(gh("api",f"repos/{repo}/commits/{p['mergeCommit']['oid']}"))["parents"][0]["sha"]
        reasons=[]
        if not tests: reasons.append("no test file in the fix")
        if not non: reasons.append("no non-test source change")
        if len(i["body"] or "")>8000: reasons.append("body > 8000 chars")
        if nondiff>150: reasons.append(f"non-test diff {nondiff} > 150")
        if deps: reasons.append("touches dependency/config files")
        rows.append({"issue":i["number"],"title":i["title"][:90],"closed":i["closedAt"][:10],"pr":p["number"],"merge":p["mergeCommit"]["oid"][:12],"parent":parent[:12],
                     "tests":len(tests),"non_test_diff":nondiff,"body_chars":len(i["body"] or ""),"excluded":"; ".join(reasons)})
        if len([r for r in rows if not r["excluded"]])>=want: break
    return rows
res={}
for repo in sys.argv[1:]:
    res[repo]=run(repo)
json.dump(res,open("/tmp/claude-1001/scan/preflight.json","w"),indent=1)
for repo,rows in res.items():
    print("==",repo,len(rows),"rows;",len([r for r in rows if not r["excluded"]]),"eligible")
