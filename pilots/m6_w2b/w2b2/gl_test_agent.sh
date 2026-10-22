#!/usr/bin/env bash
# Tests of w2b2/go_live_agent.sh on the VM, in a throwaway worktree of REF (default origin/w2b2-agent): the correct state passes
# --check-only; each broken state is refused; no run directory is created and no key is ever asked for a real run (stdin is /dev/null).
#   bash pilots/m6_w2b/w2b2/gl_test_agent.sh [REF]
set -u
REF="${1:-origin/w2b2-agent}"
WT="$HOME/w2b2a_gltest"
cd ~/Argus-agent && git fetch -q --prune
rm -rf "$WT"; git worktree prune
git worktree add -q --detach "$WT" "$REF"
cd "$WT"
cp ~/Argus-agent/.sandbox_image* .
cp -a ~/pilot3a_live/fixtures/repos/argus_p7 ~/pilot3a_live/fixtures/repos/pr_title2 fixtures/repos/
export LIVE_DIR="$PWD"
BASE=$(git rev-parse HEAD)
GL="bash pilots/m6_w2b/w2b2/go_live_agent.sh"
reset() { git reset -q --hard "$BASE"; rm -rf runs/w2b2a1; }
t() { git -c user.name=t -c user.email=t@t commit -qam "$1"; }
echo "HEAD $(git log --oneline -1)"
echo "### T0 --check-only on the correct state (must pass)"; $GL --check-only; echo "[exit $?]"; ls runs 2>&1 | head -1
echo; echo "### T1 wrong contract hash in the record (must refuse)"
sed -i 's/"contract_sha256": "4de6373c659a/"contract_sha256": "deadbeef0000/' fixtures/intake/pr_title2.json; t t1; $GL --check-only; echo "[exit $?]"; reset
echo; echo "### T2 profile large instead of default (must refuse)"
sed -i 's/"budget_profile": "default"/"budget_profile": "large"/' fixtures/contracts/pr_title2.json; t t2; $GL --check-only; echo "[exit $?]"; reset
echo; echo "### T3 contract cap 1.00 (must refuse)"
sed -i 's/"max_usd": 0.5/"max_usd": 1.0/' fixtures/contracts/pr_title2.json; t t3; $GL --check-only; echo "[exit $?]"; reset
echo; echo "### T4 pilot config edited (cap 1.00): its hash changes (must refuse)"
sed -i 's/^  max_usd: 0.50 /  max_usd: 1.00 /' pilots/m6_w2b/w2b2/config_w2b2_agent.yaml; t t4; $GL --check-only; echo "[exit $?]"; reset
echo; echo "### T5 config.yaml changed elsewhere: a third difference (must refuse)"
sed -i 's/max_workers: 3 /max_workers: 4 /' config.yaml; t t5; $GL --check-only; echo "[exit $?]"; reset
echo; echo "### T6 config.yaml turns auto_validate on: only one difference left (must refuse)"
sed -i 's/^  auto_validate: false$/  auto_validate: true/' config.yaml; t t6; $GL --check-only; echo "[exit $?]"; reset
echo; echo "### T7 the default profile changed in both configs (45,000 tokens) and the expected config hash with them: gate 3 must refuse"
sed -i 's/default: {attempt_tokens: 30000, max_output_tokens: 4096}/default: {attempt_tokens: 45000, max_output_tokens: 4096}/' config.yaml pilots/m6_w2b/w2b2/config_w2b2_agent.yaml
NEW=$(tr -d '\r' < pilots/m6_w2b/w2b2/config_w2b2_agent.yaml | sha256sum | cut -d' ' -f1)
sed -i "s/^EXPECT_CONFIG_SHA=\"[0-9a-f]*\"/EXPECT_CONFIG_SHA=\"$NEW\"/" pilots/m6_w2b/w2b2/go_live_agent.sh
t t7; $GL --check-only; echo "[exit $?]"; reset
echo; echo "### T7b config.yaml turns prompt caching on: only one difference left (must refuse)"
sed -i 's/^  prompt_cache: {enabled: false, ttl: 5m}$/  prompt_cache: {enabled: true, ttl: 5m}/' config.yaml; t t7b; $GL --check-only; echo "[exit $?]"; reset
echo; echo "### T7c the Sonnet read price back to 0.20 in both configs, expected hash updated: gate 3 must refuse"
sed -i 's/cache_read: 0.10, cache_write_5m: 2.50/cache_read: 0.20, cache_write_5m: 2.50/' config.yaml pilots/m6_w2b/w2b2/config_w2b2_agent.yaml
NEW=$(tr -d '\r' < pilots/m6_w2b/w2b2/config_w2b2_agent.yaml | sha256sum | cut -d' ' -f1)
sed -i "s/^EXPECT_CONFIG_SHA=\"[0-9a-f]*\"/EXPECT_CONFIG_SHA=\"$NEW\"/" pilots/m6_w2b/w2b2/go_live_agent.sh
t t7c; $GL --check-only; echo "[exit $?]"; reset
echo; echo "### T8 dirty tree (must refuse)"; echo x >> dirty.txt; $GL --check-only; echo "[exit $?]"; rm -f dirty.txt
echo; echo "### T9 run id exists (must refuse)"; mkdir -p runs/w2b2a1; $GL w2b2a1 </dev/null; echo "[exit $?]"; rmdir runs/w2b2a1
echo; echo "### T10 bad run ids (must refuse): the two earlier runs, another pilot, an injection"
$GL w2b2d3 </dev/null; echo "[exit $?]"; $GL w2b2a0 </dev/null; echo "[exit $?]"; $GL pilot3b1 </dev/null; echo "[exit $?]"
$GL "w2b2a1; echo hacked" </dev/null; echo "[exit $?]"
export PY="$HOME/Argus-agent/.venv-verify/bin/python"; HOME_SAVE="$HOME"; export HOME="$(mktemp -d)"
echo; echo "### T11 empty key (must refuse and start nothing)"; $GL w2b2a1 </dev/null; echo "[exit $?]"; ls runs 2>&1 | head -1
echo; echo "### T11b a key of another shape (must refuse and start nothing; fake strings, never a real key)"
printf 'not-a-key\n' | $GL w2b2a1; echo "[exit $?]"
echo; echo "### T11c a key pasted twice on one line, with a space (must refuse)"
printf 'sk-ant-fakeAAAA sk-ant-fakeBBBB\n' | $GL w2b2a1; echo "[exit $?]"
echo; echo "### T11d a key pasted twice on one line, no space (must refuse)"
printf 'sk-ant-fakeAAAAsk-ant-fakeBBBB\n' | $GL w2b2a1; echo "[exit $?]"; echo "runs after T11b-d: [$(ls runs 2>/dev/null)]"
export HOME="$HOME_SAVE"
echo; echo "### T12 no argument (must refuse)"; $GL; echo "[exit $?]"
echo; echo "### T13 correct state again (must pass)"; $GL --check-only; echo "[exit $?]"
cd ~/Argus-agent && git worktree remove --force "$WT"; git worktree prune
echo "GLTEST DONE"
