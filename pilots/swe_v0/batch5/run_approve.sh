S=/tmp/claude-1001/-home-ubuntu-Argus-agent/2a24279a-104b-449b-a4fa-96a85d905725/scratchpad/batch5
cd ~/pilot3a_live
for p in "20801 j20261029_002359_b9a1 86ce783a72bd" "20428 j20261029_002608_ad53 cb6b537a6f6c" "19954 j20261029_002951_8b7e 615460d2c68b" "19346 j20261029_003305_8bb4 a4681f9aab40"; do
  set -- $p
  ~/Argus-agent/.venv-verify/bin/python $S/spent.py $S/jobs.txt 1.00 || { echo "$1: batch cap reached, not started"; continue; }
  echo "$1: approve start $(date -u +%FT%TZ)"
  ~/Argus-agent/.venv-verify/bin/python scripts/argus.py approve $2 --sha $3 --key-file ~/.config/argus/deepseek_key --yes > $S/sympy__sympy-$1.approve.log 2>&1
  echo "$1: end $(date -u +%FT%TZ) rc=$? $(grep -E '^agent finished|^job j' $S/sympy__sympy-$1.approve.log | tr '\n' ' ')"
done
~/Argus-agent/.venv-verify/bin/python $S/spent.py $S/jobs.txt 0
echo BATCHAPPROVEDONE
