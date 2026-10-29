# grade.sh <instance number> <job>: swe_grade on the job's last agent review package, environment sympy_py39
S=/tmp/claude-1001/-home-ubuntu-Argus-agent/2a24279a-104b-449b-a4fa-96a85d905725/scratchpad/dev2
cd ~/pilot3a_live
iid=sympy__sympy-$1; J=jobs/$2
R=$(python3 -c "import json;d=json.load(open('$J/job.json'));s=[v for v in d['stages'].values() if v['kind']=='agent'][-1];print(s['review']['dir'])")
SHA=$(sha256sum $R/changes.patch | cut -d' ' -f1)
mkdir -p $S/$iid
timeout 1200 ~/Argus-agent/.venv-verify/bin/python scripts/swe_grade.py --instance ~/swe/inst/$iid --repo ~/swe/sympy --review $R --sha $SHA --environment $3 --out $S/$iid/grade.json 2>&1 | tail -2
