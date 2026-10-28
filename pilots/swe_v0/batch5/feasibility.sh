S=${S:?scratchpad}
cd ~/pilot3a_live
for iid in "$@"; do
  I=~/swe/inst/$iid
  for kind in gold empty; do
    R=$S/feas/$iid/$kind; rm -rf $R; mkdir -p $R
    if [ $kind = gold ]; then cp $I/patch.diff $R/changes.patch; else : > $R/changes.patch; fi
    SHA=$(sha256sum $R/changes.patch | cut -d' ' -f1)
    printf '{"patch": {"sha256": "%s", "files": []}}' $SHA > $R/provenance.json
    out=$(timeout 900 ~/Argus-agent/.venv-verify/bin/python scripts/swe_grade.py --instance $I --repo ~/swe/sympy --review $R --sha $SHA --environment sympy_py39 --out $R/grade.json 2>&1 | tr '\n' ' ')
    echo "$iid $kind: $out"
  done
done
echo FEASDONE
