S=/tmp/claude-1001/-home-ubuntu-Argus-agent/2a24279a-104b-449b-a4fa-96a85d905725/scratchpad
cd ~/pilot3a_live
for i in 20801 20428 19954 19346 18189; do
  iid=sympy__sympy-$i; I=~/swe/inst/$iid
  ~/Argus-agent/.venv-verify/bin/python $S/batch5/spent.py $S/batch5/jobs.txt 1.00 || { echo "$iid: batch cap reached, not started"; continue; }
  echo "$iid: start $(date -u +%FT%TZ)"
  ~/Argus-agent/.venv-verify/bin/python scripts/argus.py code --repo ~/swe/sympy --commit $(cat $I/base_commit.txt) \
    --issue-file $I/problem_statement.txt --environment sympy_py39 --key-file ~/.config/argus/deepseek_key --yes > $S/batch5/$iid.code.log 2>&1
  rc=$?
  job=$(grep -oE "^job j[0-9a-z_]+" $S/batch5/$iid.code.log | head -1 | cut -d' ' -f2)
  printf "%s %s\n" "$iid" "$job" >> $S/batch5/jobs.txt
  echo "$iid: end $(date -u +%FT%TZ) rc=$rc job=$job $(grep -E '^drafter finished|^job j' $S/batch5/$iid.code.log | tr '\n' ' ')"
done
~/Argus-agent/.venv-verify/bin/python $S/batch5/spent.py $S/batch5/jobs.txt 0
echo BATCHCODEDONE
