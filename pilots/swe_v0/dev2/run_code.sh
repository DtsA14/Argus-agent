S=/tmp/claude-1001/-home-ubuntu-Argus-agent/2a24279a-104b-449b-a4fa-96a85d905725/scratchpad/dev2
cd ~/pilot3a_live
for p in "20801 sympy_py39" "19954 sympy_py39" "24562 sympy"; do
  set -- $p; iid=sympy__sympy-$1; I=~/swe/inst/$iid
  ~/Argus-agent/.venv-verify/bin/python $S/spent.py $S/jobs.txt 1.00 || { echo "$iid: cap reached"; continue; }
  echo "$iid: start $(date -u +%FT%TZ)"
  ~/Argus-agent/.venv-verify/bin/python scripts/argus.py code --repo ~/swe/sympy --commit $(cat $I/base_commit.txt) \
    --issue-file $I/problem_statement.txt --environment $2 --key-file ~/.config/argus/deepseek_key --yes > $S/$iid.code.log 2>&1
  rc=$?
  job=$(grep -oE "^job j[0-9a-z_]+" $S/$iid.code.log | head -1 | cut -d' ' -f2)
  printf "%s %s\n" "$iid" "$job" >> $S/jobs.txt
  echo "$iid: end $(date -u +%FT%TZ) rc=$rc job=$job $(grep -E '^drafter finished|^job j' $S/$iid.code.log | tr '\n' ' ')"
done
~/Argus-agent/.venv-verify/bin/python $S/spent.py $S/jobs.txt 0
echo DEVCODEDONE
