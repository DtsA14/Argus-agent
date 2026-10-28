S=/tmp/claude-1001/-home-ubuntu-Argus-agent/2e302bbe-4da8-48cd-b0b8-acb3dfaa489a/scratchpad/batch4
cd ~/pilot3a_live
for p in "24562 j20261028_030146_c6ca 5fd55a77710c" "24066 j20261028_030554_244f 21f86863c207" "23262 j20261028_031352_c162 b087bf908863"; do
  set -- $p
  ~/Argus-agent/.venv-verify/bin/python $S/spent.py $S/jobs.txt 1.00 || { echo "$1: batch cap reached, not started"; continue; }
  echo "$1: approve start $(date -u +%FT%TZ)"
  ~/Argus-agent/.venv-verify/bin/python scripts/argus.py approve $2 --sha $3 --key-file ~/.config/argus/deepseek_key --yes > $S/sympy__sympy-$1.approve.log 2>&1
  echo "$1: end $(date -u +%FT%TZ) rc=$? $(grep -E '^agent finished|^job j' $S/sympy__sympy-$1.approve.log | tr '\n' ' ')"
done
~/Argus-agent/.venv-verify/bin/python $S/spent.py $S/jobs.txt 0
echo BATCHAPPROVEDONE
