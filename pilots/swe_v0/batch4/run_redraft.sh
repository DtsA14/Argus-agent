S=/tmp/claude-1001/-home-ubuntu-Argus-agent/2e302bbe-4da8-48cd-b0b8-acb3dfaa489a/scratchpad/batch4
until grep -q BATCHAPPROVEDONE $S/run_approve.log; do sleep 20; done
cd ~/pilot3a_live
~/Argus-agent/.venv-verify/bin/python $S/spent.py $S/jobs.txt 0.75 || { echo "22456: batch cap reached, not started"; exit 0; }
echo "22456: redraft start $(date -u +%FT%TZ)"
~/Argus-agent/.venv-verify/bin/python scripts/argus.py redraft j20261028_030915_ef15 --key-file ~/.config/argus/deepseek_key --yes > $S/sympy__sympy-22456.redraft.log 2>&1
echo "22456: end $(date -u +%FT%TZ) rc=$? $(grep -E '^drafter finished|^job j' $S/sympy__sympy-22456.redraft.log | tr '\n' ' ')"
~/Argus-agent/.venv-verify/bin/python $S/spent.py $S/jobs.txt 0
echo REDRAFTDONE
