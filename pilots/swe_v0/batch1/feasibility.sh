S=/tmp/claude-1001/-home-ubuntu-Argus-agent/d51fc756-57c7-4728-bce1-3728a84a578f/scratchpad
cd ~/Argus-agent
for iid in "$@"; do
  I=~/swe/inst/$iid
  for kind in gold empty; do
    R=$S/feas/$iid/$kind; rm -rf $R; mkdir -p $R
    if [ $kind = gold ]; then cp $I/patch.diff $R/changes.patch; else : > $R/changes.patch; fi
    SHA=$(sha256sum $R/changes.patch | cut -d' ' -f1)
    printf '{"patch": {"sha256": "%s", "files": []}}' $SHA > $R/provenance.json
    out=$(timeout 900 .venv-verify/bin/python scripts/swe_grade.py --instance $I --repo ~/swe/sympy --review $R --sha $SHA --environment sympy --out $R/grade.json 2>&1 | tr '\n' ' ')
    echo "$iid $kind: $out"
  done
done
echo FEASDONE
