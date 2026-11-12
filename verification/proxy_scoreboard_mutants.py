"""Mutants for SPEC_PROXY_SCOREBOARD: each is applied, tests/test_stage_viewer.py runs, the file is restored. Run from the repository root."""
import subprocess
F="router/stage_viewer.py"
OLD='API = re.compile(r"^/api/(summary|scoreboard|jobs|jobs/("'
MUT=[
 (OLD,'API = re.compile(r"^/api/(summary|jobs|jobs/("',"scoreboard removed from the regex"),
 (OLD,'API = re.compile(r"^/api/(summary|scoreboard/?|jobs|jobs/("',"trailing slash allowed"),
 (OLD,'API = re.compile(r"^/api/(summary|scoreboards?|jobs|jobs/("',"plural allowed"),
 (OLD,'API = re.compile(r"^/api/(summary|scoreboard.*|jobs|jobs/("',"any suffix allowed"),
 (OLD,'API = re.compile(r"^/api/(summary|(?i:scoreboard)|jobs|jobs/("',"case-insensitive"),
 (OLD,'API = re.compile(r"/api/(summary|scoreboard|jobs|jobs/("',"unanchored at the start"),
 ('return self._api(f"/{m.group(1)}") if m else self._error(404, "not found")','return self._api("/summary") if m else self._error(404, "not found")',"always asks the summary"),
 ('return self._api(f"/{m.group(1)}") if m else self._error(404, "not found")','return self._api(f"/{m.group(1)}?x=1") if m else self._error(404, "not found")',"adds a query to the upstream"),
]
bad=[]
for old,new,name in MUT:
    s=open(F).read()
    if old not in s:
        print("NOT FOUND",name,flush=True); bad.append(name); continue
    open(F,"w").write(s.replace(old,new,1))
    try:
        r=subprocess.run([".venv-verify/bin/python","-m","pytest","-q","-x","-p","no:cacheprovider","tests/test_stage_viewer.py"],capture_output=True,text=True,timeout=300)
        killed=r.returncode!=0
    except subprocess.TimeoutExpired:
        killed=True
    finally:
        open(F,"w").write(s)
    print(("KILLED  " if killed else "SURVIVED"),name,flush=True)
    if not killed: bad.append(name)
print("survivors:",bad)
