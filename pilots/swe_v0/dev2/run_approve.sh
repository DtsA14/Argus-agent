S=/tmp/claude-1001/-home-ubuntu-Argus-agent/2a24279a-104b-449b-a4fa-96a85d905725/scratchpad/dev2
cd ~/pilot3a_live
for p in "20801 j20261029_041016_4c7f e9342c7db0cb" "19954 j20261029_041320_0c02 47b2bf454b6f" "24562 j20261029_041748_2f14 a190204fd66a"; do
  set -- $p
  ~/Argus-agent/.venv-verify/bin/python $S/spent.py $S/jobs.txt 1.00 || { echo "$1: cap reached"; continue; }
  echo "$1: approve start $(date -u +%FT%TZ)"
  ~/Argus-agent/.venv-verify/bin/python scripts/argus.py approve $2 --sha $3 --key-file ~/.config/argus/deepseek_key --yes > $S/sympy__sympy-$1.approve.log 2>&1
  echo "$1: end $(date -u +%FT%TZ) rc=$? $(grep -E '^agent finished|^job j' $S/sympy__sympy-$1.approve.log | tr '\n' ' ')"
done
~/Argus-agent/.venv-verify/bin/python $S/spent.py $S/jobs.txt 0
echo DEVAPPROVEDONE
