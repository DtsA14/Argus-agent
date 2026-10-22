#!/usr/bin/env bash
# Tests of v2/go_live.sh on the VM, in a throwaway worktree of REF (default origin/m6-3a-v2-approved): the correct state passes
# --check-only; each broken state is refused; no run directory is created and no key is ever asked for a real run (stdin is /dev/null).
#   bash pilots/m6_pilot3/3a/v2/gl_test.sh [REF]
set -u
REF="${1:-origin/m6-3a-v2-approved}"
WT="$HOME/v2_gltest"
cd ~/Argus-agent && git fetch -q --prune
rm -rf "$WT"; git worktree prune
git worktree add -q --detach "$WT" "$REF"
cd "$WT"
cp ~/Argus-agent/.sandbox_image* .
cp -a ~/pilot3a_live/fixtures/repos/argus_p3 ~/pilot3a_live/fixtures/repos/fix_run_inspectors_v2 fixtures/repos/
export LIVE_DIR="$PWD"
BASE=$(git rev-parse HEAD)
GL="bash pilots/m6_pilot3/3a/v2/go_live.sh"
reset() { git reset -q --hard "$BASE"; rm -rf runs/pilot3a3; }
t() { git -c user.name=t -c user.email=t@t commit -qam "$1"; }
echo "HEAD $(git log --oneline -1)"
echo "### T0 --check-only on the correct state (must pass)"; $GL --check-only; echo "[exit $?]"; ls runs 2>&1 | head -1
echo; echo "### T1 wrong contract hash in the record (must refuse)"
sed -i 's/"contract_sha256": "ca8a521eb8b7/"contract_sha256": "deadbeef0000/' fixtures/intake/fix_run_inspectors_v2.json; t t1; $GL --check-only; echo "[exit $?]"; reset
echo; echo "### T2 profile large instead of large_usd (must refuse)"
sed -i 's/"budget_profile": "large_usd"/"budget_profile": "large"/' fixtures/contracts/fix_run_inspectors_v2.json; t t2; $GL --check-only; echo "[exit $?]"; reset
echo; echo "### T3 contract cap 1.00 (must refuse)"
sed -i 's/"max_usd": 0.75/"max_usd": 1.0/' fixtures/contracts/fix_run_inspectors_v2.json; t t3; $GL --check-only; echo "[exit $?]"; reset
echo; echo "### T4 pilot config edited (cap 1.00): its hash changes (must refuse)"
sed -i 's/^  max_usd: 0.75 /  max_usd: 1.00 /' pilots/m6_pilot3/3a/v2/config_pilot3a_v2.yaml; t t4; $GL --check-only; echo "[exit $?]"; reset
echo; echo "### T5 config.yaml changed elsewhere: a fourth difference (must refuse)"
sed -i 's/max_workers: 3 /max_workers: 4 /' config.yaml; t t5; $GL --check-only; echo "[exit $?]"; reset
echo; echo "### T6 config.yaml turns auto_validate on: only two differences left (must refuse)"
sed -i 's/^  auto_validate: false$/  auto_validate: true/' config.yaml; t t6; $GL --check-only; echo "[exit $?]"; reset
echo; echo "### T7 large_usd changed in both configs (attempt_usd 0.50) and the expected config hash with them: gate 3 must refuse"
sed -i 's/attempt_usd: 0.45, max_input_tokens: 40000/attempt_usd: 0.50, max_input_tokens: 40000/' config.yaml
sed -i 's/attempt_usd: 0.45, max_input_tokens: 40000/attempt_usd: 0.50, max_input_tokens: 40000/' pilots/m6_pilot3/3a/v2/config_pilot3a_v2.yaml
NEW=$(tr -d '' < pilots/m6_pilot3/3a/v2/config_pilot3a_v2.yaml | sha256sum | cut -d' ' -f1)
sed -i "s/^EXPECT_CONFIG_SHA=\"[0-9a-f]*\"/EXPECT_CONFIG_SHA=\"$NEW\"/" pilots/m6_pilot3/3a/v2/go_live.sh
t t7; $GL --check-only; echo "[exit $?]"; reset
echo; echo "### T8 dirty tree (must refuse)"; echo x >> dirty.txt; $GL --check-only; echo "[exit $?]"; rm -f dirty.txt
echo; echo "### T9 run id exists (must refuse)"; mkdir -p runs/pilot3a3; $GL pilot3a3 </dev/null; echo "[exit $?]"; rmdir runs/pilot3a3
echo; echo "### T10 bad run ids (must refuse): the two earlier runs, another pilot, an injection"
$GL pilot3a </dev/null; echo "[exit $?]"; $GL pilot3a2 </dev/null; echo "[exit $?]"; $GL pilot5a </dev/null; echo "[exit $?]"
$GL "pilot3a3; echo hacked" </dev/null; echo "[exit $?]"
echo; echo "### T11 empty key (must refuse and start nothing)"; $GL pilot3a3 </dev/null; echo "[exit $?]"; ls runs 2>&1 | head -1
echo; echo "### T12 no argument (must refuse)"; $GL; echo "[exit $?]"
echo; echo "### T13 correct state again (must pass)"; $GL --check-only; echo "[exit $?]"
cd ~/Argus-agent && git worktree remove --force "$WT"; git worktree prune
echo "GLTEST DONE"
