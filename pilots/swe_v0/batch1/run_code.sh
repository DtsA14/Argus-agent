S=/tmp/claude-1001/-home-ubuntu-Argus-agent/d51fc756-57c7-4728-bce1-3728a84a578f/scratchpad
cd ~/pilot3a_live
for i in 22714 23950 24213 22914 24539; do
  iid=sympy__sympy-$i; I=~/swe/inst/$iid
  ~/Argus-agent/.venv-verify/bin/python $S/batch1/spent.py $S/batch1/jobs.txt 0.75 || { echo "$iid: batch cap reached, not started"; continue; }
  echo "$iid: start $(date -u +%FT%TZ)"
  ~/Argus-agent/.venv-verify/bin/python scripts/argus.py code --repo ~/swe/sympy --commit $(cat $I/base_commit.txt) \
    --issue-file $I/problem_statement.txt --environment sympy --key-file ~/.config/argus/deepseek_key --yes > $S/batch1/$iid.code.log 2>&1
  rc=$?
  job=$(grep -oE "^job j[0-9a-z_]+" $S/batch1/$iid.code.log | head -1 | cut -d' ' -f2)
  printf "%s %s\n" "$iid" "$job" >> $S/batch1/jobs.txt
  echo "$iid: end $(date -u +%FT%TZ) rc=$rc job=$job $(grep -E '^drafter finished|^job j' $S/batch1/$iid.code.log | tr '\n' ' ')"
done
~/Argus-agent/.venv-verify/bin/python $S/batch1/spent.py $S/batch1/jobs.txt 0
echo BATCHCODEDONE
