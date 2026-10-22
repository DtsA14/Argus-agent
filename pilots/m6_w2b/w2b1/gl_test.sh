#!/usr/bin/env bash
# Tests of w2b1/go_live.sh on the VM, in a throwaway worktree of REF (default origin/w2b1-preflight): the correct state passes
# --check-only; each broken state is refused; no run directory is created and no key is ever asked for a real run (stdin is /dev/null
# or a fake string). The supervision log goes to a temporary HOME-independent file.
#   bash pilots/m6_w2b/w2b1/gl_test.sh [REF]
set -u
REF="${1:-origin/w2b1-preflight}"
WT="$HOME/w2b1_gltest"
export PY="$HOME/Argus-agent/.venv-verify/bin/python"     # fixed before the key tests change HOME
cd ~/Argus-agent && git fetch -q --prune
rm -rf "$WT"; git worktree prune
git worktree add -q --detach "$WT" "$REF"
cd "$WT"
cp ~/Argus-agent/.sandbox_image* .
P6=~/pilot3a_live/fixtures/repos/argus_p6
cp -a "$P6" fixtures/repos/
export LIVE_DIR="$PWD"
BASE=$(git rev-parse HEAD)
GL="bash pilots/m6_w2b/w2b1/go_live.sh"
C=pilots/m6_w2b/w2b1/config_w2b1.yaml
reset() { git reset -q --hard "$BASE"; rm -rf runs/w2b1d1 fixtures/repos/argus_p6; cp -a "$P6" fixtures/repos/; }
t() { git -c user.name=t -c user.email=t@t commit -qam "$1"; }
rehash() { NEW=$(tr -d '\r' < $C | sha256sum | cut -d' ' -f1); sed -i "s/^EXPECT_CONFIG_SHA=\"[0-9a-f]*\"/EXPECT_CONFIG_SHA=\"$NEW\"/" pilots/m6_w2b/w2b1/go_live.sh; }
echo "HEAD $(git log --oneline -1)"
echo "### T0 --check-only on the correct state (must pass)"; $GL --check-only; echo "[exit $?]"; ls runs 2>&1 | head -1
echo; echo "### T1 the intake changed after it was taken in (must refuse)"
echo "# changed" >> fixtures/repos/argus_p6/evals/score.py; $GL --check-only; echo "[exit $?]"; reset
echo; echo "### T2 the answer of 3b put into the intake (must refuse)"
cp ~/pilot3a_live/tests/test_pilot_report.py fixtures/repos/argus_p6/tests/ 2>/dev/null || echo "def test_x(): pass" > fixtures/repos/argus_p6/tests/test_pilot_report.py
$GL --check-only; echo "[exit $?]"; reset
echo; echo "### T3 the issue edited (must refuse)"
echo "Also add a --json flag." >> pilots/m6_w2b/w2b1/issue.txt; t t3; $GL --check-only; echo "[exit $?]"; reset
echo; echo "### T4 the pilot config edited (cap 1.00): its hash changes (must refuse)"
sed -i 's/^  max_usd: 0.75 /  max_usd: 1.00 /' $C; t t4; $GL --check-only; echo "[exit $?]"; reset
echo; echo "### T5 config.yaml changed elsewhere: a fourth difference (must refuse)"
sed -i 's/max_workers: 3 /max_workers: 4 /' config.yaml; t t5; $GL --check-only; echo "[exit $?]"; reset
echo; echo "### T6 config.yaml turns prompt caching on: only three differences left (must refuse)"
sed -i 's/^  prompt_cache: {enabled: false, ttl: 5m}$/  prompt_cache: {enabled: true, ttl: 5m}/' config.yaml; t t6; $GL --check-only; echo "[exit $?]"; reset
echo; echo "### T7 drafter attempt_usd 0.74 in both configs, expected hash updated: gate 3 must refuse"
sed -i 's/^  attempt_usd: 0.70$/  attempt_usd: 0.74/' config.yaml $C; rehash; t t7; $GL --check-only; echo "[exit $?]"; reset
echo; echo "### T8 the drafter may write, in both configs, expected hash updated: gate 3 must refuse"
sed -i 's/^  drafter: \[list_files, search_files, read_file\]/  drafter: [list_files, search_files, read_file, write_file]/' config.yaml $C
rehash; t t8; $GL --check-only; echo "[exit $?]"; reset
echo; echo "### T9 four submits in both configs, expected hash updated: gate 3 must refuse"
sed -i 's/^  max_submits: 3$/  max_submits: 4/' config.yaml $C; rehash; t t9; $GL --check-only; echo "[exit $?]"; reset
echo; echo "### T10 dirty tree (must refuse)"; echo x >> dirty.txt; $GL --check-only; echo "[exit $?]"; rm -f dirty.txt
echo; echo "### T11 run id exists (must refuse)"; mkdir -p runs/w2b1d1; $GL w2b1d1 </dev/null; echo "[exit $?]"; rmdir runs/w2b1d1
echo; echo "### T12 bad run ids (must refuse): another pilot's, zero, an injection"
$GL pilot3b1 </dev/null; echo "[exit $?]"; $GL w2b1d0 </dev/null; echo "[exit $?]"; $GL "w2b1d1; echo hacked" </dev/null; echo "[exit $?]"
export HOME_SAVE="$HOME"; export HOME="$(mktemp -d)"     # the supervision log of the key tests goes to a throwaway HOME
echo; echo "### T13 empty key (must refuse and start nothing)"; $GL w2b1d1 </dev/null; echo "[exit $?]"
echo; echo "### T13b a key of another shape (must refuse; fake strings, never a real key)"; printf 'not-a-key\n' | $GL w2b1d1; echo "[exit $?]"
echo; echo "### T13c a key pasted twice, with a space (must refuse)"; printf 'sk-ant-fakeAAAA sk-ant-fakeBBBB\n' | $GL w2b1d1; echo "[exit $?]"
echo; echo "### T13d a key pasted twice, no space (must refuse)"; printf 'sk-ant-fakeAAAAsk-ant-fakeBBBB\n' | $GL w2b1d1; echo "[exit $?]"
echo "runs after T13-T13d: [$(ls runs 2>/dev/null)]; supervision log: $(cat "$HOME/argus-supervision.log" | wc -l) lines (gates_passed only)"
grep -c key_entered "$HOME/argus-supervision.log"
export HOME="$HOME_SAVE"
echo; echo "### T14 no argument (must refuse)"; $GL; echo "[exit $?]"
echo; echo "### T15 correct state again (must pass)"; $GL --check-only; echo "[exit $?]"
cd ~/Argus-agent && git worktree remove --force "$WT"; git worktree prune
echo "GLTEST DONE"
